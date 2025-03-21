#!/usr/bin/env python3
"""
WHILL OSC Controller

This script starts an OSC server that listens for WHILL control commands,
including joystick control and power commands, and forwards them to a WHILL device.
The joystick callback interprets the first parameter as 'side' and the second as 'front'.
"""

import asyncio

import asyncclick as click
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer


# Define an abstract interface for WHILL operations.
class AbstractWHILL:
    def send_joystick(self, *, front: int, side: int) -> None:
        """Send joystick command with given front and side values."""
        raise NotImplementedError

    def send_power_on(self) -> None:
        """Send power on command."""
        raise NotImplementedError

    def send_power_off(self) -> None:
        """Send power off command."""
        raise NotImplementedError

    def send_emergency_stop(self) -> None:
        """Send emergency stop command (typically set velocity to 0)."""
        raise NotImplementedError


# Real implementation using the WHILL Python SDK.
# (Refer to WHILL/pywhill documentation for details.)
try:
    from whill import (
        ComWHILL,
    )  #  [oai_citation_attribution:0‡github.com](https://github.com/WHILL/pywhill)
except ImportError:
    ComWHILL = None


class RealWHILL(AbstractWHILL):
    def __init__(self, port: str) -> None:
        if ComWHILL is None:
            raise ImportError("whill Python SDK is not installed.")
        self.device = ComWHILL(port=port)
        print(f"Connected to WHILL device on port {port}")

    def send_joystick(self, *, front: int, side: int) -> None:
        print(f"Sending joystick command: front={front}, side={side}")
        self.device.send_joystick(front=front, side=side)

    def send_power_on(self) -> None:
        print("Sending power on command")
        self.device.send_power_on()

    def send_power_off(self) -> None:
        print("Sending power off command")
        self.device.send_power_off()

    def send_emergency_stop(self) -> None:
        print("Sending emergency stop command")
        # For example, an emergency stop might be implemented by setting both speeds to 0.
        self.device.send_joystick(front=0, side=0)


# Mock implementation for testing without real hardware.
class MockWHILL(AbstractWHILL):
    def __init__(self, port: str) -> None:
        self.port = port
        print(f"Using mock WHILL on port {port}")

    def send_joystick(self, *, front: int, side: int) -> None:
        print(f"[Mock] Joystick command received: front={front}, side={side}")

    def send_power_on(self) -> None:
        print("[Mock] Power on command received")

    def send_power_off(self) -> None:
        print("[Mock] Power off command received")

    def send_emergency_stop(self) -> None:
        print("[Mock] Emergency stop command received (set velocity to 0)")


# Controller that sets up OSC message mappings.
class WhillOSCController:
    def __init__(self, whill: AbstractWHILL) -> None:
        self.whill = whill
        self.dispatcher = Dispatcher()
        self.register_callbacks()

    def register_callbacks(self) -> None:
        """
        Register OSC callbacks for joystick control and power commands.
        """
        self.dispatcher.map("/whill/joystick", self.osc_joystick_callback)
        self.dispatcher.map("/whill/power_on", self.power_on_callback)
        self.dispatcher.map("/whill/power_off", self.power_off_callback)
        self.dispatcher.map("/whill/emergency_stop", self.emergency_stop_callback)

    def osc_joystick_callback(self, address: str, *args) -> None:
        """
        OSC callback to handle joystick messages.
        Expects at least two arguments.
        Interprets:
          - First argument as 'side'
          - Second argument as 'front'
        """
        try:
            if len(args) < 2:
                raise ValueError("At least 2 parameters required: x and y values.")
            # OSCからの値は -1 ～ 1 のスケールなので、100倍して -100 ～ 100 に変換する
            x_raw, y_raw = args[0], args[1]
            side = int(round(x_raw * 100))
            front = int(round(y_raw * 100))
            # 念のため範囲を -100～100 にクリッピングする
            side = max(min(side, 100), -100)
            front = max(min(front, 100), -100)
            print(f"[{address}] Received x: {x_raw}, y: {y_raw} => side: {side}, front: {front}")
            self.whill.send_joystick(front=front, side=side)
        except Exception as e:
            print(f"Error in OSC joystick callback: {e}")

    def power_on_callback(self, address: str, *args) -> None:
        print(f"[{address}] Power on command received")
        self.whill.send_power_on()

    def power_off_callback(self, address: str, *args) -> None:
        print(f"[{address}] Power off command received")
        self.whill.send_power_off()

    def emergency_stop_callback(self, address: str, *args) -> None:
        print(f"[{address}] Emergency stop command received")
        self.whill.send_emergency_stop()


# Command-line interface using asyncclick.
@click.command()
@click.option(
    "--serial-port",
    type=str,
    required=True,
    help="Serial port for the WHILL device (e.g. /dev/ttyUSB0)",
)
@click.option(
    "--osc-ip",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="IP address on which to bind the OSC server (default: 127.0.0.1)",
)
@click.option(
    "--osc-port",
    type=int,
    default=5005,
    show_default=True,
    help="Port number for the OSC server (default: 5005)",
)
@click.option(
    "--use-mock",
    is_flag=True,
    default=False,
    help="Use the mock WHILL implementation instead of the actual device",
)
async def main(serial_port, osc_ip, osc_port, use_mock):
    """
    WHILL OSC Controller

    This script sets up an OSC server that listens for commands on addresses:
      /whill/joystick   -> expects two numbers; interprets x as 'side' and y as 'front'
      /whill/power_on   -> turns on the WHILL
      /whill/power_off  -> turns off the WHILL
      /whill/emergency_stop -> stops the WHILL immediately (e.g. set velocity to 0)

    Serial port and OSC network settings are provided as command-line options.
    """
    # Initialize the WHILL instance.
    if use_mock:
        whill_instance = MockWHILL(serial_port)
    else:
        try:
            whill_instance = RealWHILL(serial_port)
        except Exception as e:
            print(f"Failed to initialize WHILL device: {e}")
            return

    # Create the OSC controller.
    controller = WhillOSCController(whill_instance)

    # Set up the asynchronous OSC UDP server.
    server = AsyncIOOSCUDPServer((osc_ip, osc_port), controller.dispatcher, asyncio.get_running_loop())
    transport, protocol = await server.create_serve_endpoint()
    print(f"OSC Server started on {osc_ip}:{osc_port}")

    try:
        # Keep the server running indefinitely.
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down OSC server.")
    finally:
        transport.close()


if __name__ == "__main__":
    main(_anyio_backend="asyncio")
