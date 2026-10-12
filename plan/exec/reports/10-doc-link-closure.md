# Final integration documentation-link correction

Fresh Task09 Fable artifact review accepted the actual local candidate and identified relative ADR links to plan/exec records excluded from the source distribution. Nine links in three decision documents now use the immutable public commit95b61a3ff9cbe6dc62acde75cf475958546aafc9, whose referenced record bytes are unchanged. No semantics, source, metadata or packaging inclusion changed. This three-document correction needs both final integration reviews and a fresh source archive qualification. Original candidate artifacts and reviews remain unchanged evidence.

The initial Task09 Twine error was a command transcription: `uv x` instead of the available `uvx` executable. Pinned uv0.11.29 has a working uvx shim. The supported equivalent `uv tool run --from twine==6.2.0 twine check` passed unchanged candidate bytes. It was not a tooling availability gap; original commands and reports are retained.
