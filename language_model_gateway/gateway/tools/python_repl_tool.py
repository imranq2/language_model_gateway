import logging

from langchain_core.tools import BaseTool
from langchain_experimental.utilities import PythonREPL

logger = logging.getLogger(__file__)


class PythonReplTool(BaseTool):
    name: str = "python_repl"
    description: str = (
        "A Python shell. Use this to execute python commands. Input should be a valid python command. If you want to see the output of a value, you should print it out with `print(...)`."
    )

    async def _arun(self, query: str) -> str:
        """Async implementation of the tool (in this case, just calls _run)"""
        try:
            python_repl = PythonREPL()
            logger.info(f"Running Python Repl with query: {query}")
            result: str = python_repl.run(command=query)
            logger.info(f"Python Repl result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error running Python Repl: {e}")
            logger.exception(e, stack_info=True)
            return f"Error running Python Repl: {e}"

    def _run(self, query: str) -> str:
        try:
            python_repl = PythonREPL()
            logger.info(f"Running Python Repl with query: {query}")
            result: str = python_repl.run(command=query)
            logger.info(f"Python Repl result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error running Python Repl: {e}")
            logger.exception(e, stack_info=True)
            return f"Error running Python Repl: {e}"
