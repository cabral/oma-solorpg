"""solo: a local engine for solo tabletop play. Standard library only."""


class SoloError(Exception):
    """A problem the player or the agent can fix. The CLI prints it without a traceback."""
