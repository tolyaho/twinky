class NoStreamError(Exception):
    def __init__(self, streamer_login: str):
        error_message = f"Streamlink didn't find any stream for streamer `{streamer_login}`! Maybe streamer is offline."
        Exception.__init__(self, error_message)
