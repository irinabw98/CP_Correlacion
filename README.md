<div align="center">

# 💜 CP_CORRELACION
### Correlaciones dinámicas entre variables definidas en `se_name_mod`

![Python](https://img.shields.io/badge/Python-3.11-7F3FBF?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-8A2BE2?style=for-the-badge&logo=fastapi&logoColor=white)
![Scipy](https://img.shields.io/badge/Scipy-Correlation-6A0DAD?style=for-the-badge)
![Render](https://img.shields.io/badge/Render-Online-A855F7?style=for-the-badge)
![Excel](https://img.shields.io/badge/Export-Excel-C084FC?style=for-the-badge)

Aplicación web para pegar datos desde Excel, elegir dos variables presentes en `se_name_mod`, armar pares por unidad experimental y descargar un Excel con correlaciones por grupo.

</div>

---

## ¿Qué hace esta app?

Permite:

- pegar una tabla copiada desde Excel, TSV o CSV;
- detectar columnas automáticamente;
- usar `se_name_mod` como columna dinámica de variables;
- elegir la columna numérica de valor, por ejemplo `assessment_value`;
- seleccionar Variable 1 y Variable 2 para correlacionar;
- elegir columnas de grupo, por ejemplo `trial`, `hibrido`, `dosis`;
- elegir columnas de unidad experimental para emparejar correctamente los valores, por ejemplo `plot`, `replicate_number`, `sample_id`;
- conservar columnas descriptivas adicionales;
- detectar columnas descriptivas repetidas o constantes dentro de los grupos;
- correr correlación Pearson o Spearman;
- descargar un Excel con datos emparejados, correlaciones, resumen de variables, configuración y advertencias.

---

## Ejemplo conceptual

Si la tabla viene en formato largo:

| trial | hibrido | dosis | plot | se_name_mod | assessment_value |
|---|---|---|---|---|---:|
| T1 | H1 | Alta | 1 | Fitotoxicidad (%) | 18 |
| T1 | H1 | Alta | 1 | Rendimiento Kg/ha | 9200 |
| T1 | H1 | Alta | 2 | Fitotoxicidad (%) | 22 |
| T1 | H1 | Alta | 2 | Rendimiento Kg/ha | 8700 |

La app arma internamente:

| trial | hibrido | dosis | plot | variable_1 | valor_variable_1 | variable_2 | valor_variable_2 |
|---|---|---|---|---|---:|---|---:|
| T1 | H1 | Alta | 1 | Fitotoxicidad (%) | 18 | Rendimiento Kg/ha | 9200 |
| T1 | H1 | Alta | 2 | Fitotoxicidad (%) | 22 | Rendimiento Kg/ha | 8700 |

Y calcula la correlación por las columnas de grupo seleccionadas.

---

## Recomendación para fito y rendimiento

Para responder si la fitotoxicidad se expresa luego como pérdida de rendimiento:

| Campo | Selección sugerida |
|---|---|
| Columna de variables | `se_name_mod` |
| Columna de valores | `assessment_value` |
| Variable 1 | `Fitotoxicidad (%)` |
| Variable 2 | `Rendimiento Kg/ha` |
| Grupo | `trial`, `hibrido`, `dosis` |
| Unidad experimental | `plot`, `replicate_number` o columna equivalente |
| Método | Pearson o Spearman |

Si la relación no es lineal o hay pocos datos, Spearman puede ser más robusto para interpretación exploratoria.

---

## Hojas del Excel generado

| Hoja | Contenido |
|---|---|
| `input_enriched` | tabla original con `assessment_value_num` |
| `paired_data` | tabla larga emparejada: grupo + unidad + X + Y |
| `correlations` | r, p-value, n, dirección, fuerza e interpretación |
| `variable_summary` | resumen numérico por variable seleccionada |
| `config` | configuración usada para el análisis |
| `warnings` | grupos sin pares suficientes o sin variabilidad |

---

## Estructura del proyecto

```bash
CP_CORRELACION/
├── app.py
├── app.js
├── index.html
├── styles.css
├── requirements.txt
├── runtime.txt
└── README.md
```

---

## Deploy sugerido

### Frontend

GitHub Pages con el repositorio:

```text
CP_CORRELACION
```

### Backend

Render Web Service usando:

```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

Luego actualizar en `app.js`:

```js
const API_BASE = "https://cp-correlacion.onrender.com";
```

---

## Nota importante sobre emparejamiento

La correlación necesita pares correctos. Si la tabla está en formato largo, la app usa la combinación de columnas de grupo + unidad experimental para pivotear `se_name_mod` y unir Variable 1 con Variable 2.

Si no se seleccionan columnas de unidad experimental, la app intenta usar un modo automático, pero para análisis reales se recomienda elegir al menos una columna que identifique la parcela, repetición, muestra o unidad experimental.
