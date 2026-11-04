import ast, sys, numpy as np
src = open(sys.argv[1], encoding="utf-8").read()
tree = ast.parse(src)
keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("icc21", "kalpha_interval", "varcomp", "auc")]
mod = ast.Module(body=keep, type_ignores=[])
ns = {"np": np}
from scipy import stats
ns["stats"] = stats
exec(compile(mod, "analyze_fns", "exec"), ns)
icc21, kalpha_interval, varcomp = ns["icc21"], ns["kalpha_interval"], ns["varcomp"]
X = np.random.default_rng(1).integers(1, 11, size=(50, 1))
X2 = np.hstack([X, X, X])
print("icc identical raters (expect 1.0):", round(icc21(X2), 6))
print("alpha identical raters (expect 1.0):", round(kalpha_interval(X2), 6))
# known-variance simulation: y = mu + a_t + b_j + c_r + ab + ac + bc + e
rng = np.random.default_rng(7)
n, J, R = 4000, 3, 2
sA, sB, sC, sAB, sAC, sBC, sE = 2.0, 1.0, 0.5, 0.5, 0.3, 0.2, 1.0
a = rng.normal(0, sA, n); b = rng.normal(0, sB, J); c = rng.normal(0, sC, R)
ab = rng.normal(0, sAB, (n, J)); ac = rng.normal(0, sAC, (n, R)); bc = rng.normal(0, sBC, (J, R))
e = rng.normal(0, sE, (n, J, R))
Y = 5 + a[:, None, None] + b[None, :, None] + c[None, None, :] + ab[:, :, None] + ac[:, None, :] + bc[None] + e
raw, sh = varcomp(Y)
truth = {"transcript": sA**2, "judge": sB**2, "repeat": sC**2, "transcript_x_judge": sAB**2, "transcript_x_repeat": sAC**2, "judge_x_repeat": sBC**2, "residual_3way": sE**2}
for k in truth:
    print(f"{k:22s} true={truth[k]:.3f} est={raw[k]:.3f}")
print("share sum", round(sum(sh.values()), 6))
