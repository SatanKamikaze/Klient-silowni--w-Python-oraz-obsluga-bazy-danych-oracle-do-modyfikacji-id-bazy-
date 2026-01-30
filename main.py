import sys
from PyQt5 import QtWidgets, QtCore, uic 
import oracledb


import os, pathlib


os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = str(
    pathlib.Path(QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)) / 'platforms'
)
oracledb.init_oracle_client(
    lib_dir=r"D:\SQL DEV\sqldeveloper\instantclient_23_9"
)


DB_USER = "msbd3"
DB_PASSWORD = "haslo2025"
DB_HOST = "155.158.112.45"
DB_PORT = 1521
DB_SID = "oltpstud"  

def get_connection():
    """
    Tworzy połączenie do Oracle używając SID (makedsn z sid=).
    Oracledb działa w trybie 'thin' bez dodatkowych bibliotek klienta.
    """
    dsn = oracledb.makedsn(DB_HOST, DB_PORT, sid=DB_SID)
    return oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=dsn)


class AddClientDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("Add_client.ui", self)
        
        from PyQt5.QtGui import QRegExpValidator
        from PyQt5.QtCore import QRegExp


        only_letters = QRegExp("^[A-Za-zżźćńółęąśŻŹĆĄŚĘŁÓŃ]+$")

        validator = QRegExpValidator(only_letters, self)

        self.lineImie.setValidator(validator)
        self.lineNazwisko.setValidator(validator)


        
        self.dateDolaczenia.setDate(QtCore.QDate.currentDate())
        
        self.comboKarnet.clear()
        self.comboKarnet.addItems(["Aktywny", "Nieaktywny"])

        
        try:
            self.load_regions()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Błąd", f"Nie udało się pobrać regionów:\n{e}")

        
        ok_btn = self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok)
        ok_btn.setText("Zapisz")


        self.buttonBox.accepted.connect(self._on_accept)

    def _on_accept(self):
        
        if not self.lineImie.text().strip() or not self.lineNazwisko.text().strip():
            QtWidgets.QMessageBox.warning(self, "Brak danych", "Uzupełnij Imię i Nazwisko.")
            return
        self.accept()

    def load_regions(self):
        """Załaduj listę regionów do comboRegion (format: 'SLK – Katowice')."""
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT REGION_ID, NAZWA_MIASTA FROM REGIONY_SLA ORDER BY NAZWA_MIASTA")
        self.comboRegion.clear()
        for rid, name in cur:
            self.comboRegion.addItem(f"{rid} – {name}", rid)  # userData = kod regionu
        cur.close()
        conn.close()

    def values_for_insert(self):
        """Zbierz dane z formularza w formie słownika pod bindowanie."""
        karnet_text = self.comboKarnet.currentText()
        karnet_code = 'A' if karnet_text.lower().startswith('a') else 'N'
        region_code = self.comboRegion.currentData()  # REGION_ID z userData
        return {
            "imie": self.lineImie.text().strip(),
            "nazwisko": self.lineNazwisko.text().strip(),
            "wiek": int(self.spinWiek.value()),
            "staz": int(self.spinStaz.value()),
            "karnet": karnet_code,
            "region": region_code,
            "data": self.dateDolaczenia.date().toString("yyyy-MM-dd")
        }


class DeleteClientDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("Usun.ui", self)
        ok_btn = self.buttonBox.button(QtWidgets.QDialogButtonBox.Ok)
        ok_btn.setText("Usuń")

    def client_id(self):
        return int(self.spinClientID.value())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("Projekt.ui", self)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._update_clock)
        self.timer.start(1000)
        self._update_clock()

        
        self._prepare_table()

       
        self.btnShowClients.clicked.connect(self.export_clients_to_txt)
        self.btnSortRegion.clicked.connect(lambda: self.load_clients(order_by="REGION"))
        self.btnAddClient.clicked.connect(self.add_client)
        self.btnDeleteClient.clicked.connect(self.delete_client)

        self.load_clients()
        self.sort_by_region = False

    
    def _prepare_table(self):
        headers = ["ID", "Imię", "Nazwisko", "Wiek", "Staż (mies.)", "Karnet", "Region", "Data dołączenia"]
        self.tableWidget.setColumnCount(len(headers))
        self.tableWidget.setHorizontalHeaderLabels(headers)
        self.tableWidget.setRowCount(0)
        self.tableWidget.horizontalHeader().setStretchLastSection(True)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

    def _update_clock(self):
        now = QtCore.QDateTime.currentDateTime()
        self.lblDateTime.setText(now.toString("yyyy-MM-dd HH:mm:ss"))

    def _msg(self, text, kind="info"):
        if kind == "error":
            QtWidgets.QMessageBox.critical(self, "Błąd", text)
        elif kind == "warn":
            QtWidgets.QMessageBox.warning(self, "Uwaga", text)
        else:
            self.statusBar().showMessage(text, 3000)

    
    def load_clients(self, order_by=None):
        """
        Ładuje klientów do tabeli.
        order_by=None -> bez sortowania
        order_by="REGION" -> sortuj wg nazwy miasta
        """
        try:
            conn = get_connection()
            cur = conn.cursor()
            sql = """
                SELECT 
                    k.KLIENT_ID,
                    k.IMIE,
                    k.NAZWISKO,
                    k.WIEK,
                    k.STAZ_MIES,
                    CASE k.KARNET_STATUS WHEN 'A' THEN 'Aktywny' ELSE 'Nieaktywny' END AS KARNET,
                    r.NAZWA_MIASTA AS REGION,
                    TO_CHAR(k.DATA_DOLACZENIA, 'YYYY-MM-DD') AS DATA_DOL
                FROM KLIENCI k
                JOIN REGIONY_SLA r ON r.REGION_ID = k.REGION_ID
            """
            if order_by == "REGION":
                sql += " ORDER BY r.NAZWA_MIASTA, k.NAZWISKO"
            else:
                sql += " ORDER BY k.KLIENT_ID"

            cur.execute(sql)
            rows = cur.fetchall()

            self.tableWidget.setRowCount(0)
            for r, row in enumerate(rows):
                self.tableWidget.insertRow(r)
                for c, val in enumerate(row):
                    item = QtWidgets.QTableWidgetItem(str(val))
                    item.setFlags(item.flags() ^ QtCore.Qt.ItemIsEditable)
                    self.tableWidget.setItem(r, c, item)

            cur.close()
            conn.close()
            self._msg(f"Załadowano {len(rows)} klientów.")
        except Exception as e:
            self._msg(f"Nie udało się pobrać klientów:\n{e}", "error")

    def add_client(self):
        dlg = AddClientDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            data = dlg.values_for_insert()
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO KLIENCI
                        (IMIE, NAZWISKO, WIEK, STAZ_MIES, KARNET_STATUS, REGION_ID, DATA_DOLACZENIA)
                    VALUES
                        (:imie, :nazwisko, :wiek, :staz, :karnet, :region, TO_DATE(:data,'YYYY-MM-DD'))
                """, data)
                conn.commit()
                cur.close()
                conn.close()
                self._msg("Dodano klienta.")
                self.load_clients()
            except Exception as e:
                self._msg(f"Nie udało się dodać klienta:\n{e}", "error")

    def delete_client(self):
        dlg = DeleteClientDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            cid = dlg.client_id()
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute("DELETE FROM KLIENCI WHERE KLIENT_ID = :id", {"id": cid})
                deleted = cur.rowcount
                conn.commit()
                cur.close()
                conn.close()
                if deleted:
                    self._msg(f"Usunięto klienta ID={cid}.")
                else:
                    self._msg(f"Nie znaleziono klienta ID={cid}.", "warn")
                self.load_clients()
            except Exception as e:
                self._msg(f"Nie udało się usunąć klienta:\n{e}", "error")

    def export_clients_to_txt(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    k.KLIENT_ID,
                    k.IMIE,
                    k.NAZWISKO,
                    k.WIEK,
                    k.STAZ_MIES,
                    CASE k.KARNET_STATUS WHEN 'A' THEN 'Aktywny' ELSE 'Nieaktywny' END AS KARNET,
                    r.NAZWA_MIASTA AS REGION,
                    TO_CHAR(k.DATA_DOLACZENIA, 'YYYY-MM-DD') AS DATA_DOL
                FROM KLIENCI k
                JOIN REGIONY_SLA r ON r.REGION_ID = k.REGION_ID
                ORDER BY k.KLIENT_ID
            """)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            with open("klienci.txt", "w", encoding="utf-8") as f:
                
                header = f"{'ID':<4} {'Imię':<12} {'Nazwisko':<15} {'Wiek':<5} {'Staż':<6} {'Karnet':<10} {'Region':<15} {'Data doł':<12}\n"
                f.write(header)
                f.write("-" * len(header) + "\n")

                
                for row in rows:
                    line = f"{row[0]:<4} {row[1]:<12} {row[2]:<15} {row[3]:<5} {row[4]:<6} {row[5]:<10} {row[6]:<15} {row[7]:<12}\n"
                    f.write(line)

            QtWidgets.QMessageBox.information(self, "Eksport", "Dane klientów zapisane do klienci.txt")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Błąd", f"Nie udało się pobrać klientów:\n{e}")


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
