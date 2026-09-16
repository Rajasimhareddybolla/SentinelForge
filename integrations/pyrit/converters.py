"""Prompt converter utilities wrapping Microsoft PyRIT obfuscation and encoding converters."""

import logging
from typing import Dict, List, Optional

from pyrit.converter import (
    Base64Converter,
    CharacterSpaceConverter,
    Converter,
    LeetspeakConverter,
    ROT13Converter,
    StringJoinConverter,
)

logger = logging.getLogger("sentinelforge.pyrit.converters")


class PyritConverterSuite:
    """Provides high-level prompt transformation and obfuscation via PyRIT converters."""

    def __init__(self):
        self._converters: Dict[str, Converter] = {
            "rot13": ROT13Converter(),
            "base64": Base64Converter(),
            "char_space": CharacterSpaceConverter(),
            "leetspeak": LeetspeakConverter(),
            "hyphen_join": StringJoinConverter(join_value="-"),
        }

    @property
    def available_converters(self) -> List[str]:
        """Returns list of registered converter names."""
        return list(self._converters.keys())

    async def convert(self, prompt: str, converter_name: str) -> str:
        """Transforms prompt with the specified converter.

        Args:
            prompt: Original prompt text.
            converter_name: Identifier of converter (rot13, base64, char_space, leetspeak, hyphen_join).

        Returns:
            Transformed text string.
        """
        name = converter_name.lower().strip()
        if name not in self._converters:
            logger.warning("Converter '%s' not recognized; returning original prompt.", converter_name)
            return prompt

        converter = self._converters[name]
        res = await converter.convert_async(prompt=prompt)
        return res.output_text

    async def apply_chain(self, prompt: str, converter_names: List[str]) -> str:
        """Sequentially applies multiple converters to a prompt."""
        current = prompt
        for name in converter_names:
            current = await self.convert(current, name)
        return current

