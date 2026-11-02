"""Inicializador independente da Biblioteca de Mods (janela de teste)."""
from __future__ import annotations

import tkinter as tk

from biblioteca_mods import BibliotecaMods


def main():
    root=tk.Tk()
    root.withdraw()
    window=BibliotecaMods(root)
    def close():
        window.close()
        root.destroy()
    window.protocol("WM_DELETE_WINDOW",close)
    root.mainloop()


if __name__=="__main__":
    main()
