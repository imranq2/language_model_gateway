import logging
import os
import time
from typing import Dict, List, cast

from fastapi import HTTPException
from openai.types import CompletionUsage
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionMessageParam,
    ChatCompletion,
    ChatCompletionMessage,
    ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion import Choice
from starlette.responses import StreamingResponse, JSONResponse

from language_model_gateway.configs.config_reader.config_reader import ConfigReader
from language_model_gateway.configs.config_schema import ChatModelConfig, PromptConfig
from language_model_gateway.gateway.providers.base_chat_completions_provider import (
    BaseChatCompletionsProvider,
)
from language_model_gateway.gateway.providers.langchain_chat_completions_provider import (
    LangChainCompletionsProvider,
)
from language_model_gateway.gateway.providers.openai_chat_completions_provider import (
    OpenAiChatCompletionsProvider,
)
from language_model_gateway.gateway.schema.openai.completions import ChatRequest

logger = logging.getLogger(__name__)


class ChatCompletionManager:
    """
    Implements the chat completion manager following the OpenAI API
    https://platform.openai.com/docs/overview
    https://github.com/openai/openai-python/blob/main/api.md


    """

    def __init__(
        self,
        *,
        open_ai_provider: OpenAiChatCompletionsProvider,
        langchain_provider: LangChainCompletionsProvider,
        config_reader: ConfigReader,
    ) -> None:
        """
        Chat completion manager

        :param open_ai_provider: provider to use for OpenAI completions
        :param langchain_provider: provider to use for LangChain completions
        :return:
        """

        self.openai_provider: OpenAiChatCompletionsProvider = open_ai_provider
        assert self.openai_provider is not None
        assert isinstance(self.openai_provider, OpenAiChatCompletionsProvider)
        self.langchain_provider: LangChainCompletionsProvider = langchain_provider
        assert self.langchain_provider is not None
        assert isinstance(self.langchain_provider, LangChainCompletionsProvider)
        self.config_reader: ConfigReader = config_reader
        assert self.config_reader is not None
        assert isinstance(self.config_reader, ConfigReader)

    # noinspection PyMethodMayBeStatic
    async def chat_completions(
        self,
        *,
        headers: Dict[str, str],
        chat_request: ChatRequest,
    ) -> StreamingResponse | JSONResponse:
        # Use the model to choose the provider

        model: str = chat_request["model"]
        assert model is not None

        configs: List[ChatModelConfig] = (
            await self.config_reader.read_model_configs_async()
        )

        # Find the model config
        model_config: ChatModelConfig | None = next(
            (config for config in configs if config.name.lower() == model.lower()), None
        )
        if model_config is None:
            logger.error(f"Model {model} not found in the config")
            raise HTTPException(
                status_code=400, detail=f"Model {model} not found in the config"
            )

        chat_request = self.add_system_messages(
            chat_request=chat_request, system_prompts=model_config.system_prompts
        )

        provider: BaseChatCompletionsProvider
        match model_config.type:
            case "openai":
                provider = self.openai_provider
            case "langchain":
                provider = self.langchain_provider
            case _:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model type {model_config.type} not supported",
                )

        logger.info(f"Running chat completion for {chat_request}")
        # Use the provider to get the completions
        return await provider.chat_completions(
            model_config=model_config, headers=headers, chat_request=chat_request
        )

    # noinspection PyMethodMayBeStatic
    def add_system_messages(
        self, chat_request: ChatRequest, system_prompts: List[PromptConfig] | None
    ) -> ChatRequest:
        # see if there are any system prompts in chat_request
        has_system_messages_in_chat_request: bool = any(
            [
                message
                for message in chat_request["messages"]
                if message["role"] == "system"
            ]
        )
        if (
            not has_system_messages_in_chat_request
            and system_prompts is not None
            and len(system_prompts) > 0
        ):
            system_messages: List[ChatCompletionSystemMessageParam] = [
                ChatCompletionSystemMessageParam(role="system", content=message.content)
                for message in system_prompts
                if message.role == "system" and message.content is not None
            ]
            chat_request["messages"] = system_messages + [
                r for r in chat_request["messages"]
            ]

        return chat_request

    # noinspection PyMethodMayBeStatic
    def handle_help_prompt(
        self, *, chat_request: ChatRequest, model: str, model_config: ChatModelConfig
    ) -> StreamingResponse | JSONResponse | None:
        request_messages: List[ChatCompletionMessageParam] = [
            m for m in chat_request["messages"]
        ]
        if request_messages is None:
            logger.error("Messages not found in the request")
            raise HTTPException(
                status_code=400, detail="Messages not found in the request"
            )

        user_messages: List[ChatCompletionUserMessageParam] = [
            m for m in request_messages if m["role"] == "user"
        ]
        if user_messages is None or len(user_messages) == 0:
            logger.error("User messages not found in the request")
            raise HTTPException(
                status_code=400, detail="User messages not found in the request"
            )

        last_message_content: str = cast(str, user_messages[-1]["content"])
        logger.info(
            f"Last message content: {last_message_content}, type: {type(last_message_content)}"
        )

        if isinstance(
            last_message_content, str
        ) and last_message_content.lower() == os.environ.get("HELP_KEYWORD", "/help"):
            logger.info(f"Help requested for model {model}")
            response_messages: List[ChatCompletionMessage] = [
                ChatCompletionMessage(
                    role="assistant",
                    content=model_config.description or "No description available",
                )
            ]
            if model_config.example_prompts is not None:
                response_messages.extend(
                    [
                        ChatCompletionMessage(role="assistant", content=prompt.content)
                        for prompt in model_config.example_prompts
                    ]
                )

            choices: List[Choice] = [
                Choice(index=i, message=m, finish_reason="stop")
                for i, m in enumerate(response_messages)
            ]
            chat_response: ChatCompletion = ChatCompletion(
                id="1",
                model=chat_request["model"],
                choices=choices,
                usage=CompletionUsage(
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                ),
                created=int(time.time()),
                object="chat.completion",
            )
            logger.info(f"Returning help response: {chat_response.model_dump()}")
            if chat_request.get("stream"):
                return StreamingResponse(content=chat_response.model_dump())
            else:
                return JSONResponse(content=chat_response.model_dump())

        return None
