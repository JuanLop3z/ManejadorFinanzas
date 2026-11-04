"""Native desktop entry point. No browser or web server required."""
import sys
import json
from PySide6.QtWidgets import QApplication, QMessageBox
from config.settings import DATABASE_PATH, ROOT
from database.connection import create_database
from desktop.main_window import MainWindow
from desktop.theme import apply_theme
from services.finance_service import seed_examples
from services.expense_service import import_evidence


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Mi plan")
    app.setOrganizationName("Mi plan local")
    apply_theme(app)
    engine = None
    try:
        engine = create_database(DATABASE_PATH)
        seed_examples(engine)
        evidence = ROOT / "data" / "gmail_evidence_2026.json"
        if evidence.exists():
            import_evidence(engine, json.loads(evidence.read_text(encoding="utf-8")))
        window = MainWindow(engine)
        window.show()
        return app.exec()
    except Exception as error:
        QMessageBox.critical(None, "No se pudo iniciar Mi plan", str(error))
        return 1
    finally:
        app.shutdown()
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
