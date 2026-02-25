import logging
from typing import Dict, Optional

from app.domain.messaging.core import MessageTemplate
from app.services.flow.types import FlowType

from .operations import NotFoundError

logger = logging.getLogger(__name__)


class FlowCoreTemplateBindingMixin:
    async def get_message_template_for_day(
        self, flow_type: FlowType, day: int
    ) -> Optional[MessageTemplate]:
        try:
            from app.services.template_loader_pkg import FlowTemplateData, TemplateLoadError

            try:
                flow_template: FlowTemplateData = self.template_loader.load_flow_template(
                    flow_type.value
                )
            except TemplateLoadError as exc:
                logger.error(f"Template load error for {flow_type.value}: {exc}.")
                raise NotFoundError(f"Template load error for {flow_type.value}") from exc
            except FileNotFoundError as exc:
                logger.error(f"Template file not found for {flow_type.value}: {exc}.")
                raise NotFoundError(f"Template file not found for {flow_type.value}") from exc
            except Exception:
                logger.error(
                    f"Unexpected error loading template {flow_type.value}",
                    exc_info=True,
                )
                raise

            if day in flow_template.messages:
                message_template = flow_template.messages[day]
                logger.debug(f"Found message template for {flow_type.value} day {day}")
                return message_template

            logger.warning(f"No message template found for {flow_type.value} day {day}.")
            raise NotFoundError(
                f"No message template found for {flow_type.value} day {day}"
            )

        except Exception as exc:
            logger.error(
                f"Critical error getting message template for {flow_type.value} day {day}: {exc}.",
                exc_info=True,
            )
            raise

    async def reload_templates(self, flow_type: Optional[str] = None) -> Dict[str, str]:
        try:
            results: Dict[str, str] = {}

            if flow_type:
                await self.template_cache.invalidate_template_cache(flow_type)
                template = await self.template_cache.get_template(flow_type)
                results[flow_type] = "reloaded" if template else "not_found"
            else:
                from app.services.flow_template import FlowTemplateService

                template_service = FlowTemplateService(self.db)
                templates = template_service.get_all_templates()
                for template in templates:
                    await self.template_cache.invalidate_template_cache(template.flow_type)
                    results[template.flow_type] = "reloaded"

            logger.info(f"Templates reloaded: {list(results.keys())}")
            return results

        except Exception as exc:
            logger.error(f"Failed to reload templates: {exc}")
            return {"error": str(exc)}
