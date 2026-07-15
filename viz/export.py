"""Plotly → PNG para el reporte PDF, con degradación elegante si falta kaleido."""
import io

def plotly_png_array(fig, scale=2):
    """Devuelve un array RGBA (para imshow de matplotlib) o None si kaleido no está / falla."""
    try:
        import matplotlib.image as mpimg
        png = fig.to_image(format="png", scale=scale)  # requiere kaleido
        return mpimg.imread(io.BytesIO(png))
    except Exception:
        return None
