import socket

import pytest
from pytest_socket import SocketConnectBlockedError


# pytest-socket emits this warning on every blocked attempt; here the attempt is the point.
@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket.connect:UserWarning")
def test_connecting_to_an_external_host_is_blocked() -> None:
    # A public IP literal avoids DNS, so the only thing under test is the pytest-socket guard.
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("93.184.216.34", 80), timeout=1)
