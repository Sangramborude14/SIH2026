# SIH26001: Technical Specification & Mathematical Formulation Reference

## 1. Mathematical Risk Scoring Formulation

The authoritative Landslide Risk Score $R \in [0, 100]$ is computed deterministically through a multi-signal normalized weighted linear combination with saturation penalties:

$$R = \min\left(100.0, \, \sum_{i=1}^{n} w_i \cdot f_i(x_i) + \Omega_{\text{persistence}} + \Omega_{\text{anomaly}}\right)$$

### Factor Breakdown & Weights:
1. **24-Hour Precipitation Factor ($f_1$, $w_1 = 0.35$):**
   $$f_1(P_{24}) = \min\left(100.0, \, \frac{P_{24}}{150.0} \times 100\right)$$
2. **72-Hour Antecedent Precipitation Factor ($f_2$, $w_2 = 0.15$):**
   $$f_2(P_{72}) = \min\left(100.0, \, \frac{P_{72}}{300.0} \times 100\right)$$
3. **Soil Moisture Saturation Ratio ($f_3$, $w_3 = 0.20$):**
   $$f_3(\theta) = \min\left(100.0, \, \frac{\theta}{100.0} \times 100\right)$$
4. **Terrain Slope Incline Factor ($f_4$, $w_4 = 0.15$):**
   $$f_4(\alpha) = \min\left(100.0, \, \frac{\alpha}{60.0} \times 100\right)$$
5. **Geological Susceptibility Factor ($f_5$, $w_5 = 0.15$):**
   $$f_5(S) = S \times 100$$

### Saturation & Persistence Modifiers:
* **Precipitation Persistence Multiplier ($\Omega_{\text{persistence}}$):**
  $$\Omega_{\text{persistence}} = \begin{cases} +12.5 & \text{if } P_{24} \ge 100\text{mm} \land \theta \ge 85\% \\ +6.0 & \text{if } P_{24} \ge 65\text{mm} \land \theta \ge 75\% \\ 0 & \text{otherwise} \end{cases}$$
* **Anomaly Z-Score Boost ($\Omega_{\text{anomaly}}$):**
  $$\Omega_{\text{anomaly}} = \begin{cases} +10.0 & \text{if } Z_{\text{rain}} \ge 3.0 \\ +5.0 & \text{if } Z_{\text{rain}} \ge 2.0 \\ 0 & \text{otherwise} \end{cases}$$

---

## 2. Risk Level Classifications & Confidence Estimation

### Risk Levels:
* **`CRITICAL`:** $R \ge 75.0$ (Immediate mass movement imminent)
* **`HIGH`:** $55.0 \le R < 75.0$ (High slope instability)
* **`MODERATE`:** $35.0 \le R < 55.0$ (Heightened moisture surveillance)
* **`LOW`:** $R < 35.0$ (Normal baseline stability)

### Signal Agreement Confidence ($C \in [0.4, 0.98]$):
$$C = 0.85 - 0.15 \times \text{StdDev}(f_1, f_2, f_3, f_4, f_5) + \text{Bonus}_{\text{live\_telemetry}}$$

---

## 3. Event Lifecycle State Machine & Hysteresis

To eliminate alert flicker from momentary sensor fluctuations, event state transitions enforce **strict threshold hysteresis**:

```text
[DETECTED]  ──(Risk >= 75.0)──►  [ACTIVE]
                                    │
                                (Risk < 50.0 for 2 cycles)
                                    ▼
                               [MITIGATED]
                                    │
                                (Risk < 35.0)
                                    ▼
                               [RESOLVED]
```

* **Escalation to `CRITICAL`:** Triggered immediately when $R \ge 75.0$.
* **Downgrade to `MODERATE`:** Requires $R < 50.0$ (25-point hysteresis buffer) to avoid premature stand-down.
* **Closure to `RESOLVED`:** Requires $R < 35.0$.

---

## 4. AI/ML Predictive Analytics Formulation & Task Separation

The system formally decouples **Environmental Anomaly Detection (Task A)** from **Landslide Occurrence Probability Forecasting (Task B)**:

### Task A: Environmental Anomaly Model Formulation
Quantifies statistical unorthodoxy of hydrometeorological telemetry relative to historical baseline:
$$A_{\text{env}} = w_{\text{rain}} \cdot A_{\text{rain}}(Z_P, P_{1h}) + w_{\text{soil}} \cdot A_{\text{soil}}(\theta, \dot{\theta}) + w_{\text{hydro}} \cdot A_{\text{hydro}}(I / I_{\text{crit}}, API)$$

* $A_{\text{env}} \in [0.0, 1.0]$, classified as `NORMAL` ($<0.30$), `ELEVATED` ($0.30 - 0.60$), `SEVERE` ($0.60 - 0.85$), or `EXTREME` ($\ge 0.85$).
* **Invariant:** An extreme environmental anomaly signifies abnormal moisture/rainfall, but does NOT by itself constitute a slope failure forecast.

### Task B: Landslide Occurrence Probability Formulation
Estimates the conditional probability of slope failure within a specific future forecast horizon $H \in \{6\,\text{h}, 12\,\text{h}, 24\,\text{h}\}$:
$$P(Y_{t+H} = 1 \mid \mathbf{X}_t) = \sigma\left(\mathbf{w}_H^T \phi(\mathbf{X}_t) + b_H\right)$$

Where $\mathbf{X}_t$ represents the 15-dimensional standardized feature vector:
1. `slope_angle` (Static topographic gradient, °)
2. `elevation` (Static elevation ASL, m)
3. `baseline_susceptibility` (Static geological vulnerability index, 0–1)
4. `rainfall_1h`, `rainfall_6h`, `rainfall_24h`, `rainfall_72h` (Precipitation accumulation windows, mm)
5. `soil_moisture_surface`, `soil_moisture_middle`, `soil_moisture_deep` (Pore saturation strata, %)
6. `antecedent_precipitation_index` (Decaying moisture index, API)
7. `consecutive_wet_hours` (Continuous precipitation duration, h)
8. `rainfall_z_score_24h` (Standardized departure, $\sigma$)
9. `soil_moisture_trend_slope` (Saturation infiltration rate, %/step)
10. `id_curve_ratio` (Intensity-Duration critical threshold ratio)

### Strict Data Provenance Classification
Every feature attribute must carry immutable provenance metadata:
* **`OBSERVED`:** Real-time sensor gauge or live API measurement.
* **`FORECAST`:** Numerical weather prediction (NWP) model output.
* **`SATELLITE`:** Earth Observation remote sensing (ISRO Bhoonidhi / Sentinel).
* **`MODEL_DERIVED`:** Deterministically computed physical indicators (API, I-D ratio).
* **`STATIC`:** Survey DEM / geological susceptibility maps.
* **`SIMULATED`:** Synthetic testing or backtesting fixtures.

---

## 5. Agentic AI Guardrails & Scientific Invariance


The system implements the **Scientific Invariance Guardrail**:

```text
   ENVIRONMENTAL TELEMETRY
              ↓
   DETERMINISTIC SCIENTIFIC ENGINE  ◄─── (Authoritative Source of Truth)
              ↓
     STRUCTURED RISK ASSESSMENT
              ↓
     AGENTIC AI REASONING LAYER     ◄─── (Read-Only Interpretation & Explanation)
              ↓
     EXPERT & PUBLIC EXPLANATIONS
```

### Invariant Rules:
1. Large Language Models (LLMs) are **read-only observers**. They cannot alter risk scores, change event statuses, or delete logs.
2. AI responses cite specific numerical sensor evidence ($P_{24}$, $\theta$, $\alpha$, $Z$).
3. All AI queries produce an immutable entry in `ai_audit_logs`.

---

## 6. Common Alerting Protocol (CAP v1.2) Compliance

The CAP export engine implements the **OASIS Standard CAP v1.2 / ITU-T X.1303**:
* **XML Namespace:** `urn:oasis:names:tc:emergency:cap:1.2`
* **Mandatory Tags:** `identifier`, `sender`, `sent`, `status`, `msgType`, `scope`, `category`, `event`, `urgency`, `severity`, `certainty`, `headline`, `description`, `instruction`, `area`, `circle`.
* **Disaster Parameters:**
  * `disaster_risk_score`: Formatted score $0.0 - 100.0$.
  * `engine_confidence`: Signal agreement metric $0.00 - 1.00$.
  * `hazard_type`: Specific landslide classification.
  * `data_mode`: Provenance tag (`LIVE` vs `SIMULATION`).

---

## 7. North Eastern Region Geographical Coordinates


* **Gangtok, Sikkim:** $27.3389^\circ\text{N}, 88.6065^\circ\text{E}$ (Slope: $38.5^\circ$)
* **Haflong, Assam:** $25.1764^\circ\text{N}, 93.0177^\circ\text{E}$ (Slope: $34.0^\circ$)
* **Aizawl, Mizoram:** $23.7271^\circ\text{N}, 92.7176^\circ\text{E}$ (Slope: $42.0^\circ$)
* **Imphal / Noney, Manipur:** $24.8170^\circ\text{N}, 93.9368^\circ\text{E}$ (Slope: $29.5^\circ$)
* **Shillong, Meghalaya:** $25.5788^\circ\text{N}, 91.8933^\circ\text{E}$ (Slope: $31.0^\circ$)
* **Itanagar, Arunachal Pradesh:** $27.0844^\circ\text{N}, 93.6053^\circ\text{E}$ (Slope: $36.0^\circ$)
