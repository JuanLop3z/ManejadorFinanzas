"""Render native widgets offscreen for a local visual check."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from config.settings import DATABASE_PATH, ROOT
from database.connection import create_database
from desktop.main_window import MainWindow
from desktop.theme import apply_theme


def main():
    app = QApplication([])
    apply_theme(app)
    engine = create_database(DATABASE_PATH)
    window = MainWindow(engine)
    window.show()
    output = ROOT / "data" / "preview"
    output.mkdir(parents=True, exist_ok=True)

    def capture():
        for page in ["Resumen", "Mi presupuesto", "Gastos de Gmail"]:
            window.navigate(page)
            app.processEvents()
            window.grab().save(str(output / (page.replace(" ", "_") + ".png")))
            if page == "Resumen":
                window.scroll.verticalScrollBar().setValue(window.scroll.verticalScrollBar().maximum())
                app.processEvents()
                window.grab().save(str(output / "Distribucion.png"))
        window.close()
        app.quit()

    QTimer.singleShot(200, capture)
    app.exec()
    app.shutdown()
    engine.dispose()
    print(output)


if __name__ == "__main__":
    main()
