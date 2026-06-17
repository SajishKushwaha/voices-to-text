import logging

from flask import Flask, jsonify
from flask_cors import CORS

from .config import Settings
from .database import init_database
from .routes.health import health_bp
from .routes.pdf import pdf_bp
from .routes.stream import init_stream_socket, stream_bp
from .routes.transcribe import transcribe_bp
from .routes.transcripts import transcripts_bp


def create_app(settings: Settings | None = None) -> Flask:
    resolved_settings = settings or Settings()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = resolved_settings.max_content_length_bytes
    app.config["SETTINGS"] = resolved_settings

    configure_logging(resolved_settings)
    init_database(resolved_settings)
    CORS(app, resources={r"/api/*": {"origins": resolved_settings.cors_origins}})

    app.register_blueprint(health_bp)
    app.register_blueprint(transcribe_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(transcripts_bp)
    init_stream_socket(app)

    @app.errorhandler(413)
    def file_too_large(_error):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Audio file is too large.",
                    "code": "FILE_TOO_LARGE",
                }
            ),
            413,
        )

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        app.logger.exception("Unhandled API error: %s", error)
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Unexpected server error.",
                    "code": "INTERNAL_SERVER_ERROR",
                }
            ),
            500,
        )

    return app


def configure_logging(settings: Settings) -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
