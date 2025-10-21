import logging
from slangpy_imgui_bundle.app import App

if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)

    app = App()
    app.run()
