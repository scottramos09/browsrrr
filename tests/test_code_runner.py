from browsrrr.code_runner import SubprocessCodeRunner


def test_runs_python_code():
    runner = SubprocessCodeRunner(timeout_seconds=20)

    result = runner.run_python("print('browsrrr-ok')")

    assert result.returncode == 0
    assert "browsrrr-ok" in result.stdout


def test_reports_stderr():
    runner = SubprocessCodeRunner(timeout_seconds=20)

    result = runner.run_python("import sys; sys.stderr.write('bad')")

    assert "bad" in result.stderr