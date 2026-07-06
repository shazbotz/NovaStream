"""Parses an HTTP `Range` request header for the `/stream/{media_id}`
handler in `server.py`.

Pulled out into its own pure function (no aiohttp, no I/O) so this one
piece of new, easy-to-get-wrong-at-the-edges logic (single-range
`bytes=start-end` requests only - multi-range and suffix-only ranges like
`bytes=-500` are the two trickiest cases) can be unit tested directly,
without needing aiohttp installed or a running server. `server.py`'s
`stream()` handler is the only caller.
"""

from __future__ import annotations

from dataclasses import dataclass


class MalformedRangeError(ValueError):
    pass


class UnsatisfiableRangeError(ValueError):
    pass


@dataclass(frozen=True)
class ByteRange:
    start: int
    end: int  # inclusive
    is_partial: bool


def parse_range(range_header: str | None, file_size: int) -> ByteRange:
    """Returns the (inclusive) byte range to serve.

    - No `Range` header (or one that isn't a `bytes=` range): the whole
      file, `is_partial=False`.
    - `bytes=START-END`: exactly that inclusive range.
    - `bytes=START-` (open-ended): from START to the end of the file.
    - `bytes=-SUFFIX` (suffix range, e.g. "last 500 bytes"): the final
      SUFFIX bytes of the file - this is what most video players send
      first to probe a file's tail (e.g. for MP4 moov-atom-at-end files),
      so it has to work, not just the common `start-end` case.

    Raises `MalformedRangeError` for a header that isn't parseable as
    integers, and `UnsatisfiableRangeError` for a well-formed range that
    doesn't fit inside `[0, file_size)` (start > end, or end/start beyond
    the file) - the caller maps these to 400 and 416 respectively.
    """
    if not range_header or not range_header.startswith("bytes="):
        return ByteRange(start=0, end=max(file_size - 1, 0), is_partial=False)

    spec = range_header[len("bytes=") :]
    if "," in spec:
        # Multi-range requests are legal HTTP but no client this platform
        # targets (mobile Mini App video/audio players, browser <video>)
        # sends them for progressive media - treat as unsupported rather
        # than silently only serving the first range.
        raise MalformedRangeError("Multi-range requests are not supported")

    start_s, _, end_s = spec.partition("-")
    try:
        if start_s == "" and end_s == "":
            raise MalformedRangeError("Empty range")
        if start_s == "":
            # Suffix range: last `end_s` bytes.
            suffix_len = int(end_s)
            if suffix_len <= 0:
                raise MalformedRangeError("Suffix range length must be positive")
            start = max(file_size - suffix_len, 0)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s != "" else file_size - 1
    except ValueError as exc:
        if isinstance(exc, MalformedRangeError):
            raise
        raise MalformedRangeError(f"Could not parse Range header '{range_header}'") from exc

    if file_size <= 0 or start > end or start < 0 or end >= file_size:
        raise UnsatisfiableRangeError(f"Range '{range_header}' not satisfiable for size {file_size}")

    return ByteRange(start=start, end=end, is_partial=True)
