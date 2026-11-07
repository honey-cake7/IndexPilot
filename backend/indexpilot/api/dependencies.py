from fastapi import Request

from indexpilot.metadata.session import metadata_engine


def get_engine(request: Request):
    with request.app.state.metadata_lock:
        if request.app.state.metadata_engine is None:
            request.app.state.metadata_engine = metadata_engine(request.app.state.settings)
        return request.app.state.metadata_engine
