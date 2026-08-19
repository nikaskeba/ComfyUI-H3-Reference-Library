import re

import numpy as np
import torch
from PIL import Image, ImageOps

import comfy.model_management
from comfy_extras.nodes_audio import load as load_audio_file

from .library import library_revision, media_path, records_by_tag


MAX_IMAGES = 9
MAX_AUDIO = 3
TAG_RE = re.compile(r"\{([A-Za-z0-9_-]+)\}")
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth")


def _subject_reference(tag, records, image_indexes):
    number = image_indexes[tag] + 1
    subject = f"<Subject {number}>"
    if records[tag].get("category", "").startswith("character"):
        subject += f" (S{number})"
    return subject


def _description(record, kind, tag):
    return (record.get(f"{kind}_description") or tag).strip().rstrip(".")


def resolve_prompt(prompt_template, records):
    ordered_tags = []
    seen = set()
    for match in TAG_RE.finditer(prompt_template):
        tag = match.group(1)
        if tag not in seen:
            seen.add(tag)
            ordered_tags.append(tag)

    if not ordered_tags:
        return prompt_template, "", [], []

    missing = [tag for tag in ordered_tags if tag not in records]
    if missing:
        raise ValueError(f"H3 reference library has no record for tag '{{{missing[0]}}}'.")

    paired_tags = [
        tag for tag in ordered_tags
        if records[tag].get("image_file") and records[tag].get("audio_file")
    ]
    image_tags = paired_tags + [
        tag for tag in ordered_tags
        if records[tag].get("image_file") and not records[tag].get("audio_file")
    ]
    audio_candidates = paired_tags + [
        tag for tag in ordered_tags
        if records[tag].get("audio_file") and not records[tag].get("image_file")
    ]
    audio_tags = audio_candidates[:MAX_AUDIO]
    if len(image_tags) > MAX_IMAGES:
        raise ValueError(f"H3 supports at most {MAX_IMAGES} reference images; this prompt uses {len(image_tags)}.")
    image_indexes = {tag: index for index, tag in enumerate(image_tags)}
    audio_indexes = {tag: index for index, tag in enumerate(audio_tags)}

    def replace_tag(match):
        tag = match.group(1)
        if tag in image_indexes:
            return _subject_reference(tag, records, image_indexes)
        if tag in audio_indexes:
            return f"<Audio {audio_indexes[tag] + 1}>"
        return _description(records[tag], "audio", tag)

    rewritten = TAG_RE.sub(replace_tag, prompt_template).strip()
    legends = []
    mapping = []
    for tag in image_tags:
        record = records[tag]
        image_index = image_indexes[tag]
        subject = _subject_reference(tag, records, image_indexes)
        legend = (
            f"{subject} is defined by the {ORDINALS[image_index]} reference image: "
            f"{_description(record, 'image', tag)}."
        )
        mapping_line = f"{{{tag}}} -> {subject}"
        if tag in audio_indexes:
            audio = f"<Audio {audio_indexes[tag] + 1}>"
            legend += (
                f" {audio} is the voice-timbre reference for {subject}: "
                f"{_description(record, 'audio', tag)}."
            )
            mapping_line += f", voice {audio}"
        elif record.get("audio_file"):
            legend += f" {subject} speaks with {_description(record, 'audio', tag)}."
            mapping_line += ", voice described in prompt"
        legends.append(legend)
        mapping.append(mapping_line)

    for tag in audio_candidates:
        if tag in image_indexes:
            continue
        if tag in audio_indexes:
            audio = f"<Audio {audio_indexes[tag] + 1}>"
            legends.append(f"{audio} is the standalone voice or sound reference: {_description(records[tag], 'audio', tag)}.")
            mapping.append(f"{{{tag}}} -> {audio}")
        else:
            description = _description(records[tag], "audio", tag)
            legends.append(f"The standalone voice or sound for {{{tag}}} is described as {description}.")
            mapping.append(f"{{{tag}}} -> {description} (described in prompt)")

    return "\n".join(legends) + "\n\n" + rewritten, "\n".join(mapping), image_tags, audio_tags


def load_image(path):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        array = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array).unsqueeze(0)
    return tensor.to(
        device=comfy.model_management.intermediate_device(),
        dtype=comfy.model_management.intermediate_dtype(),
    )


def load_audio(path):
    waveform, sample_rate = load_audio_file(str(path))
    return {"waveform": waveform.unsqueeze(0), "sample_rate": sample_rate}


class H3TaggedReferencePrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_template": ("STRING", {
                    "multiline": True,
                    "default": "[Shot 1] {news_anchor} is sitting at {news_desk}.",
                    "tooltip": "Prompt text using tags managed in the H3 Reference Library, such as {news_anchor}.",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING") + ("IMAGE",) * MAX_IMAGES + ("AUDIO",) * MAX_AUDIO
    RETURN_NAMES = (
        ("prompt", "mapping")
        + tuple(f"image_{i}" for i in range(1, MAX_IMAGES + 1))
        + tuple(f"audio_{i}" for i in range(1, MAX_AUDIO + 1))
    )
    FUNCTION = "build"
    CATEGORY = "video/text"

    @classmethod
    def IS_CHANGED(cls, prompt_template):
        return f"{library_revision()}:{prompt_template}"

    def build(self, prompt_template):
        records = records_by_tag()
        prompt, mapping, image_tags, audio_tags = resolve_prompt(prompt_template or "", records)

        images = [load_image(media_path(records[tag], "image")) for tag in image_tags]
        audios = [load_audio(media_path(records[tag], "audio")) for tag in audio_tags]
        images.extend([None] * (MAX_IMAGES - len(images)))
        audios.extend([None] * (MAX_AUDIO - len(audios)))
        return (prompt, mapping, *images, *audios)
