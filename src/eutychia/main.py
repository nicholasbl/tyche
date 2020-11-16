
# Import modules and functions.

import os
import sys
sys.path.insert(0, os.path.abspath(".."))

import json    as json
import numpy   as np
import pandas  as pd
import quart   as qt
import seaborn as sb
import tyche   as ty
import uuid    as uuid

from base64            import b64encode
from io                import BytesIO
from matplotlib.figure import Figure


# Create and configure application.

app = qt.Quart(
  __name__                  ,
  static_url_path = ""      ,
  static_folder   = "static",
)

app.config.from_file("demo.json", json.load)


# Compute investments.

investments = ty.Investments(app.config["INVESTMENTS"])

designs = ty.Designs(app.config["DESIGNS"])
designs.compile()

tranche_results = investments.evaluate_tranches(designs, sample_count = 25)

evaluator = ty.Evaluator(investments.tranches, tranche_results.summary)

optimizer = ty.EpsilonConstraintOptimizer(evaluator)

metric_range = evaluator.min_metric.apply(
  lambda x: np.minimum(0, x)
).join(
  evaluator.max_metric.apply(
    lambda x: np.maximum(0, x)
  ),
  lsuffix = " Min",
  rsuffix = " Max",
)


# Session-level storage.

session_amounts = {}
session_evaluation = {}


# Main page.

@app.route("/")
async def explorer():
  ident = uuid.uuid4()
  qt.session["ID"] = ident
  amounts = evaluator.amounts.groupby(
    "Category"
  ).max(
  ).apply(
    lambda x: x[0] / 2, axis = 1
  ).rename(
    "Amount"
  ).to_frame(
  )
  session_amounts[ident] = amounts
  session_evaluation[ident] = evaluator.evaluate(amounts)
  return await qt.render_template(
    "model.html"                     ,
    categories = evaluator.max_amount["Amount"],
    metrics    = metric_range                  ,
    units      = evaluator.units["Units"]      ,
    plot_types = ["box plot", "distribution"]  ,
  )


# Generate plots.

@app.route("/plot", methods = ["POST"])
async def plot():
  ident = qt.session["ID"]
  evaluation = session_evaluation[ident]
  form = await qt.request.form

  typ = str(form["plottype"])

  m = evaluator.metrics[int(form["met"])]
  c = None if form["cat"] == "x" else evaluator.categories[int(form["cat"])]
  figure = Figure(figsize=(float(form["width"]) / 100, float(form["height"]) / 100))
  ax = figure.subplots()
  summary = evaluation.xs(m, level = "Index")
  if c is None:
    values = summary.groupby("Sample").sum()
  else:
    values = summary.xs(c, level = "Category")
  y0 = min(0, metric_range.loc[m, "Value Min"])
  y1 = max(0, metric_range.loc[m, "Value Max"])
  dy = (y1 - y0) / 20
  if typ == "box plot":
    sb.boxplot(x = values, ax = ax)
    # sb.stripplot(y = values, ax = ax)
    ax.set(
      # xlabel = str(m)              ,
      # ylabel = str(c)              ,
      xlabel = "",
      ylabel = "",
      xlim = (y0 - dy, y1 + dy),
    )
    localdir = "box"
  elif typ == "distribution":
    sb.distplot(values, hist = False, ax = ax)
    ax.set(
      # xlabel      = str(m)            ,
      # ylabel      = str(c)            ,
      xlabel = "",
      ylabel = "",
      yticks      = []                ,
      yticklabels = []                ,
      xlim        = (y0 - dy, y1 + dy),
    )
    localdir = "dist"
#   sb.stripplot(y = values, ax = ax, alpha=.5)
#   ax.set(
#     xlabel = ""              ,
#     ylabel = ""              ,
#     ylim = (y0 - dy, y1 + dy),
#   )
  figure.set_tight_layout(True)
  # Save locally -- for prototyping.
  localpath = os.path.join("assets","plots",localdir,(str(m) + "_" + str(c).split()[0] + ".png").lower())
  figure.savefig(localpath)
  # Save for server.
  img = BytesIO()
  figure.savefig(img, format="png")
  img.seek(0)
  x = b64encode(img.getvalue())
  return "data:image/png;base64,{}".format(x.decode("utf-8"))

# Comptue metrics.

@app.route("/metric", methods = ["POST"])
async def metric():
  ident = qt.session["ID"]
  evaluation = session_evaluation[ident]
  form = await qt.request.form
  m = evaluator.metrics[int(form["met"])]
  return str(
    np.mean(
      evaluation.xs(
        m, level = "Index"
      ).groupby(
        "Sample"
      ).aggregate(
        np.sum
      )
    )
  )


# Update investment and recompute.

@app.route("/invest", methods = ["POST"])
async def invest():
  ident = qt.session["ID"]
  form = await qt.request.form
  c = int(form["cat"])
  v = float(form["value"])
  session_amounts[ident].loc[evaluator.categories[c]] = v
  session_evaluation[ident] = evaluator.evaluate(session_amounts[ident])
  return ""


# Optimize investments.

@app.route("/optimize", methods = ["POST"])
async def optimize():
  ident = qt.session["ID"]
  evaluation = session_evaluation[ident]
  form = await qt.request.form
  target_metric = evaluator.metrics[int(form["target"])]
  print(target_metric)
  constraints = json.loads(form["constraints"])
  min_metric = pd.Series(
    [constraints["metric"]["metlimwid_" + str(m)] for m in range(len(evaluator.metrics))]
  , index = evaluator.metrics
  )
  max_amount = pd.Series(
    [constraints["invest"]["invlimwid_" + str(m)] for m in range(len(evaluator.categories))]
  , index = evaluator.categories
  )
  total_amount = constraints["invest"]["invlimwid_x"]
  optimum = optimizer.maximize(
    metric       = target_metric
  , min_metric   = min_metric
  , max_amount   = max_amount
  , total_amount = total_amount
# , tol          = 1e-4
# , maxiter      = 10
  )
  amounts = pd.DataFrame(optimum.amounts)
  session_amounts[ident] = amounts
  session_evaluation[ident] = evaluator.evaluate(amounts)
  result = {}
  result["message"] = optimum.exit_message
  result["amount"] = {
    "invoptwid_" + str(m) : optimum.amounts[m]
    for m in range(len(optimum.amounts))
  }
  return json.dumps(result)