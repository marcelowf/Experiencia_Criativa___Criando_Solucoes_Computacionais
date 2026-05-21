import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from controllers.app_controller import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host='0.0.0.0', port=8080, debug=True)