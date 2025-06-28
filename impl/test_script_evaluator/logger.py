from datetime import datetime
from fpdf import FPDF
import os


class Logger:
    def __init__(self, log_format="txt", output_dir="Results"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_format = log_format.lower()
        self.messages = []

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        filename = f"test_results_{timestamp}.{self.log_format}"
        self.file_path = os.path.join(output_dir, filename)

        if self.log_format == "pdf":
            self.pdf = FPDF()
            self.pdf.add_page()
            self.pdf.set_font("Arial", size=12)

        elif self.log_format == "html":
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("<html><body><h1>FHIR Test Log</h1>\n")

        elif self.log_format == "txt":
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(f"FHIR Test Log - {datetime.now()}\n\n")

    def log(self, message):
        print(message)
        self.messages.append(message)

        if self.log_format == "pdf":
            self.pdf.multi_cell(0, 10, message)

        elif self.log_format == "html":
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"<p>{message}</p>\n")

        elif self.log_format == "txt":
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(message + "\n")

    def close(self):
        if self.log_format == "pdf":
            self.pdf.output(self.file_path)
        elif self.log_format == "html":
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write("</body></html>")
