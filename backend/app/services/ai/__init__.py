"""AI document review using Google Gemini (free tier).

Reads each scanned PDF, writes a very short overview, and categorizes it into
the user's discovered businesses and folder categories. Falls back silently to
the keyword matcher when no API key is configured. Claude/Anthropic is
intentionally not supported in this app.
"""
