from PySide2.QtCore import QTranslator

# Crie um objeto QTranslator
translator = QTranslator()

# Carregue o arquivo '.ts'
translator.load("i18n/avenza_kmz_importer_en.ts")

# Compile o arquivo '.ts' em um arquivo '.qm'
translator.save("i18n/avenza_kmz_importer_en.qm")


