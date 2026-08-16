import pytest

from browsrrr.external_apps import ExternalAppError, SubprocessExternalAppLauncher


def test_rejects_empty_command():
    launcher = SubprocessExternalAppLauncher()

    with pytest.raises(ExternalAppError):
        launcher.launch("   ")