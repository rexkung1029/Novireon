from typing import Any, Iterator, List, Literal, Optional, Sequence, SupportsInt, Union


def hyperlink(text: str, url: str) -> str:
    """Create hyperlink markdown with text and a URL.

    Args:
        text (str): The text which will contain the link.
        url (str): The URL used for the hyperlink.

    Returns:
        str: The hyperlink message.
    """
    return f"[{text}]({url})"


def header(text: str, size: Literal["small", "medium", "large"]) -> str:
    """Formats a header.

    Args:
        text (str): The text for the header.
        size (Literal[&quot;small&quot;, &quot;medium&quot;, &quot;large&quot;]): The size of the header

    Returns:
        str: The header message
    """
    match size:
        case "small":
            m = 3
        case "medium":
            m = 2
        case "large":
            m = 1
    return "#" * m + " " + text
