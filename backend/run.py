from app import create_app

app = create_app()

celery = app.celery


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=(
            app.config["DEBUG"]
            and app.config["APP_ENV"].lower() == "development"
        )
    )
