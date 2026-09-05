import unittest
from unittest.mock import patch

from integrated_qa_system import main as entrypoint


class MainEntryPointTest(unittest.TestCase):
    def test_no_arguments_starts_web_server(self):
        with patch("uvicorn.run") as run:
            entrypoint.main([])

        run.assert_called_once_with(
            "integrated_qa_system.web.app:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )

    def test_all_commands_are_dispatched_by_the_same_entry_point(self):
        command_cases = (
            ("chat", "run_chat"),
            ("index", "run_index"),
            ("faq", "run_faq"),
        )

        for command, handler_name in command_cases:
            with self.subTest(command=command):
                with patch.object(entrypoint, handler_name) as handler:
                    entrypoint.main([command])

                handler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
