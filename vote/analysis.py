#!script

def logistic_regression(X, Y, exclude_features = set()):
  # Transform X from a list of dicts of factors to
  # a matrix with a defined order. Also transform
  # True to 1, False to -1, and None to 0. (We don't
  # do the same for Y because Logit requires Y in
  # [0, 1].)
  def to_number(value):
    if value is True: return 1
    if value is False: return -1
    if value is None: return 0
    return value
  from itertools import chain
  features = set(chain.from_iterable(set(x.keys()) for x in X))
  features -= exclude_features
  if len(features) == 0:
    return None
  features = sorted(features)
  X = [
    [to_number(x[key]) for key in features]
    for x in X
  ]

  # Run regression.

  #from statsmodels.api import OLS
  #model = OLS(Y, X)

  from statsmodels.discrete.discrete_model import Logit
  model = Logit(Y, X)
  import warnings
  with warnings.catch_warnings():
    warnings.filterwarnings("ignore", message="Perfect separation")
    warnings.filterwarnings("ignore", message="divide by zero encountered")
    warnings.filterwarnings("ignore", message="overflow encountered in exp")
    warnings.filterwarnings("ignore", message="HessianInversionWarning")
    try:
      # method='bfgs' avoids Singular Matrix which is very common for
      # binary data where features may be linear combinations of other
      # features
      fit = model.fit(method='bfgs', maxiter=100, disp=False, warn_convergence=False) # disp silences stdout
      rsquared = float(fit.prsquared) # .rsquared for OLS; for Logit this can also throw PerfectSeparationError
    except:
    	# various errors can be thrown
      return None
  #if not fit.converged: return None # not in old version currently installed

  # Transform results back into a dictionary.
  return {
    "rsquared": rsquared,
    "features": {
      feature: {
        "value": float(fit.params[i]),
        "pvalue": float(fit.pvalues[i])
      }
      for i, feature in enumerate(features)
    }
  }


def logistic_regression_fit_best_model(X, Y):
  # Remove features iteratively from the model
  # that are non-significant
  exclude_features = set()
  repeat = True
  last_fit_model = None
  while repeat:
    repeat = False
    model = logistic_regression(X, Y, exclude_features=exclude_features)
    if model is None:
      break
    last_fit_model = model
    for feature, params in model["features"].items():
      if feature == "intercept": continue # don't remove this one
      if params["pvalue"] > .025:
        exclude_features.add(feature)
        repeat = True
        break # only remove one feature at a time
  return last_fit_model


