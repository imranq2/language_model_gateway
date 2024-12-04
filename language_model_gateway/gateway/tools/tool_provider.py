from os import environ
from typing import Dict

from langchain_community.tools import (
    DuckDuckGoSearchRun,
    ArxivQueryRun,
)
from langchain_core.tools import BaseTool

from language_model_gateway.configs.config_schema import ToolConfig
from language_model_gateway.gateway.image_generation.image_generator_factory import (
    ImageGeneratorFactory,
)
from language_model_gateway.gateway.tools.current_time_tool import CurrentTimeTool
from langchain_community.tools.pubmed.tool import PubmedQueryRun

from language_model_gateway.gateway.tools.google_search_tool import GoogleSearchTool
from language_model_gateway.gateway.tools.graph_viz_diagram_generator_tool import (
    GraphVizDiagramGeneratorTool,
)
from language_model_gateway.gateway.tools.image_generator_embedded_tool import (
    ImageGeneratorEmbeddedTool,
)
from language_model_gateway.gateway.tools.python_repl_tool import PythonReplTool
from language_model_gateway.gateway.tools.url_to_markdown_tool import URLToMarkdownTool


class ToolProvider:
    def __init__(self, *, image_generator_factory: ImageGeneratorFactory) -> None:
        web_search_tool: BaseTool
        default_web_search_tool: str = environ.get(
            "DEFAULT_WEB_SEARCH_TOOL", "duckduckgo"
        )
        match default_web_search_tool:
            case "duckduckgo_search":
                web_search_tool = DuckDuckGoSearchRun()
            case "google_search":
                web_search_tool = GoogleSearchTool()
            case _:
                raise ValueError(
                    f"Unknown default web search tool: {default_web_search_tool}"
                )

        self.tools: Dict[str, BaseTool] = {
            "current_date": CurrentTimeTool(),
            "web_search": web_search_tool,
            "pubmed": PubmedQueryRun(),
            "google_search": GoogleSearchTool(),
            "duckduckgo_search": DuckDuckGoSearchRun(),
            "python_repl": PythonReplTool(),
            "get_web_page": URLToMarkdownTool(),
            "arxiv_search": ArxivQueryRun(),
            "image_generator": ImageGeneratorEmbeddedTool(
                image_generator_factory=image_generator_factory
            ),
            "graph_viz_diagram_generator": GraphVizDiagramGeneratorTool(),
            # "sql_query": QuerySQLDataBaseTool(
            #     db=SQLDatabase(
            #         engine=Engine(
            #             url=environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
            #             pool=Pool(),
            #             dialect=Dialect()
            #         )
            #     )
            # ),
        }

    def get_tool_by_name(self, *, tool: ToolConfig) -> BaseTool:
        if tool.name in self.tools:
            return self.tools[tool.name]
        raise ValueError(f"Tool with name {tool.name} not found")

    def get_tools(self, *, tools: list[ToolConfig]) -> list[BaseTool]:
        return [self.get_tool_by_name(tool=tool) for tool in tools]
