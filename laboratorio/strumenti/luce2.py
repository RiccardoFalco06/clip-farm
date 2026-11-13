"""Luce che pulsa sopra il video: componente di luminosità comune a tutto il quadro, tolta la tendenza lenta (media mobile 1 s).
Riporta ampiezza (rms, luma 0-255), periodo dominante (autocorrelazione), e come agisce: quanto sale nei blocchi scuri
e in quelli chiari quando il quadro si schiarisce, quanto scende quando si scurisce. In flusso, 48x64.
uso: python3 -I luce2.py video ..."""
import sys
import numpy as np
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from luce import blocchi

for v in sys.argv[1:]:
    b = blocchi(v)
    k = np.ones(31) / 31
    lento = np.array([np.convolve(b[:, i], k, mode="same") for i in range(16)]).T
    r = (b - lento)[15:-15]
    g = np.median(r, axis=1)
    a = np.correlate(g - g.mean(), g - g.mean(), "full")[len(g) - 1:]
    a /= a[0]
    lag = next((i for i in range(2, 30) if a[i] > a[i - 1] and a[i] >= a[i + 1]), None)  # primo picco dopo lo zero
    m = lento[15:-15]
    su, giu = g > 2, g < -2
    scuri, chiari = m < 70, m > 170
    f = lambda sel, area: round(float(r[sel][:, :][area[sel]].mean()), 1) if sel.any() and area[sel].any() else None
    print(v.rsplit("/", 1)[-1], {"rms": round(float(g.std()), 2), "periodo_s": round(lag / 30, 2) if lag else None,
          "picco_autoc": round(float(a[lag]), 2) if lag else None, "su_scuri": f(su, scuri), "su_chiari": f(su, chiari),
          "giu_scuri": f(giu, scuri), "giu_chiari": f(giu, chiari), "frazione_su": round(float(su.mean()), 2), "frazione_giu": round(float(giu.mean()), 2)})
