import logging
import os
from contextlib import asynccontextmanager
from os import makedirs, environ
from pathlib import Path
from typing import AsyncGenerator, Annotated, List

from fastapi import FastAPI, HTTPException
from fastapi.params import Depends
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from language_model_gateway.configs.config_reader.config_reader import ConfigReader
from language_model_gateway.configs.config_schema import ChatModelConfig
from language_model_gateway.gateway.api_container import get_config_reader
from language_model_gateway.gateway.routers.chat_completion_router import (
    ChatCompletionsRouter,
)
from language_model_gateway.gateway.routers.image_generation_router import (
    ImageGenerationRouter,
)
from language_model_gateway.gateway.routers.models_router import ModelsRouter

# warnings.filterwarnings("ignore", category=LangChainBetaWarning)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app1: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: This runs when the first request comes in
    worker_id = id(app)
    try:
        # Configure logging
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        print(f"Starting application initialization for worker {worker_id}...")

        # perform any startup tasks here

        print(f"Application initialization completed for worker {worker_id}")
        yield

    except Exception as e:
        logger.exception(e, stack_info=True)
        raise

    finally:
        try:
            print(f"Starting application shutdown for worker {worker_id}...")
            # await container.cleanup()
            # Clean up on shutdown
            print("Data cleaned up")
            print("Application shutdown completed")
        except Exception as e:
            logger.exception(e, stack_info=True)
            raise


def create_app() -> FastAPI:
    app1: FastAPI = FastAPI(title="OpenAI-compatible API", lifespan=lifespan)
    app1.include_router(ChatCompletionsRouter().get_router())
    app1.include_router(ModelsRouter().get_router())
    app1.include_router(ImageGenerationRouter().get_router())
    # Mount the static directory
    app1.mount(
        "/static",
        StaticFiles(
            directory="/usr/src/language_model_gateway/language_model_gateway/static"
        ),
        name="static",
    )

    image_generation_path: str = environ["IMAGE_GENERATION_PATH"]

    assert (
        image_generation_path is not None
    ), "IMAGE_GENERATION_PATH environment variable must be set"

    makedirs(image_generation_path, exist_ok=True)

    app1.mount(
        "/image_generation",
        StaticFiles(directory=image_generation_path),
        name="static",
    )
    return app1


# Create the FastAPI app instance
app = create_app()


@app.get("/health")
async def health() -> str:
    return "OK"


@app.get("/favicon.png", include_in_schema=False)
async def favicon() -> FileResponse:
    # Get absolute path
    file_path = Path("language_model_gateway/static/bwell-web.png")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)


@app.get("/refresh")
async def refresh_data(
    request: Request, config_reader: Annotated[ConfigReader, Depends(get_config_reader)]
) -> JSONResponse:
    assert config_reader is not None
    assert isinstance(config_reader, ConfigReader)
    await config_reader.clear_cache()
    configs: List[ChatModelConfig] = await config_reader.read_model_configs_async()
    return JSONResponse({"message": "Configuration refreshed", "data": configs})
