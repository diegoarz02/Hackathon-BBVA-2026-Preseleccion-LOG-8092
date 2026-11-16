"""Estilo de figuras (skill dataviz): paleta categorica validada con orden fijo, color = entidad, marcas finas,
rejilla recesiva, sin doble eje, textos pequenos y etiquetas directas SIN solapes (``repel``)."""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8b8a85", "#e8e7e3"
# paleta categorica validada (orden fijo; slot = entidad)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"
CAT = [BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED]
# color fijo por ENTIDAD
COL = {
    "final": BLUE, "ganador": BLUE, "policy": BLUE, "incumbente": BLUE,
    "starter": ORANGE, "baseline": ORANGE,
    "ref_price": AQUA, "ref_eta": YELLOW, "ref_mix": MAGENTA, "default": VIOLET,
    "grid": VIOLET, "random": AQUA, "sobol": YELLOW, "tpe": BLUE, "cmaes": MAGENTA,
}
PRODUCT_COL = {"STANDARD": BLUE, "SME": ORANGE, "BUSINESS": AQUA, "VIP_BLACK": YELLOW}
# mapas continuos (un solo matiz claro->oscuro; divergente con punto medio neutro)
SEQ = mpl.colors.LinearSegmentedColormap.from_list("seq_blue", ["#eef4fc", "#b7d3f6", "#5598e7", "#256abf", "#0d366b"])
DIV = mpl.colors.LinearSegmentedColormap.from_list("div_ob", [ORANGE, "#f6c9b3", "#f0efec", "#b7d3f6", BLUE])
GOOD_BAD = mpl.colors.ListedColormap(["#f3c9c2", "#cfe8d8"])


def apply():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.titlecolor": INK, "axes.titleweight": "bold", "axes.titlesize": 9, "axes.titlelocation": "left",
        "axes.titlepad": 7, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7, "font.size": 7.5,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.6, "lines.markersize": 4.5,
        "legend.frameon": False, "legend.fontsize": 7, "legend.handlelength": 1.4, "legend.borderaxespad": 0.2,
        "figure.dpi": 110, "savefig.dpi": 160, "savefig.bbox": "tight", "savefig.pad_inches": 0.12,
        "figure.constrained_layout.use": True, "figure.titlesize": 10, "figure.titleweight": "bold",
        "font.family": "DejaVu Sans",
    })


def color(name: str) -> str:
    return COL.get(name, VIOLET)


def repel(ax, xs, ys, texts, fontsize=6.2, color=INK2, offset=(4, 4), iters=60, **kw):
    """Etiqueta puntos y separa las etiquetas que se solapan (repulsion vertical iterativa en coordenadas de pantalla)."""
    fig = ax.figure
    anns = [ax.annotate(t, (x, y), xytext=offset, textcoords="offset points", fontsize=fontsize, color=color, **kw)
            for x, y, t in zip(xs, ys, texts)]
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    shifts = [float(offset[1])] * len(anns)
    for _ in range(iters):
        moved = False
        boxes = [a.get_window_extent(rend) for a in anns]
        for i in range(len(anns)):
            for j in range(i + 1, len(anns)):
                if boxes[i].overlaps(boxes[j]):
                    d = (boxes[i].y1 - boxes[j].y0) / 2 + 0.5 if boxes[i].y0 >= boxes[j].y0 else -((boxes[j].y1 - boxes[i].y0) / 2 + 0.5)
                    step = 0.55 * np.sign(d) * min(abs(d), 6) * 72 / fig.dpi
                    shifts[i] += step
                    shifts[j] -= step
                    anns[i].set_position((offset[0], shifts[i]))
                    anns[j].set_position((offset[0], shifts[j]))
                    moved = True
                    boxes = [a.get_window_extent(rend) for a in anns]
        if not moved:
            break
    return anns


def panel_label(ax, text, x=0.0, y=1.02, **kw):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=8.5, fontweight="bold", color=INK, va="bottom", **kw)
