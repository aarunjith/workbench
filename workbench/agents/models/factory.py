from .base_llm import ModelConfig
from logging import getLogger
import importlib

logger = getLogger(__name__)


class ModelFactory:

    @staticmethod
    def create(model_config: ModelConfig):
        # try:
        class_name = f"{model_config.provider.capitalize()}Model"
        logger.info(f"Initialising {class_name} Model")
        module = importlib.import_module(
            f"workbench.agents.models.{model_config.provider}"
        )
        class_ = getattr(module, class_name)
        instance = class_(model_config)
        return instance

    # except (ImportError, AttributeError):
    #     raise NotImplementedError(f"Model {model_config.model_name} is undefined")
