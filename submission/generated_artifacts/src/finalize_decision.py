"""Cierra la decision de la 2.a corrida: escribe en v2_decision.json los parametros EXPLICITOS de la propuesta final (los del archivo
candidate_strategy.py) y el motivo. Con el generador fiel ningun candidato supera de forma robusta al incumbente, asi que se conserva."""
import ast, json, re
import sim_harness as H

C = H.REPO / "solucion" / "outputs" / "csvs"
src = (H.REPO / "candidate_strategy.py").read_text(encoding="utf-8")
block = re.search(r"^PARAMS = (\{.*?^\})", src, re.S | re.M).group(1)
params = ast.literal_eval(block)
dec = json.load(open(C / "v2_decision.json"))
dec["params_ganador"] = params
dec["ganador_final"] = "incumbente"
dec["motivo"] = ("Con escenarios fieles a los datos reales (desfase de llegadas dentro del cluster ~ U(0, 45 min)) ningun candidato del re-ajuste supera de forma robusta "
                 "(IC95 inferior > 0 en puntos por percentil) a las constantes de la 1.a corrida; se conservan, con el bucle de despacho corregido.")
json.dump(dec, open(C / "v2_decision.json", "w"), indent=1)
print("decision cerrada:", {k: params[k] for k in ("w_time", "hold_cap_min", "la_tau")})
