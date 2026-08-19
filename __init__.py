from .h3_tag_references import H3TaggedReferencePrompt
from .server import register_routes


register_routes()

NODE_CLASS_MAPPINGS = {
    "H3TaggedReferencePrompt": H3TaggedReferencePrompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3TaggedReferencePrompt": "H3 Tagged Reference Prompt",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
