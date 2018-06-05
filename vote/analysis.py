#!script

import numpy as np
from scipy.optimize.optimize import fmin_cg, fmin_bfgs, fmin

from vote.views import load_ideology_scores

# Adapted from:
# http://blog.smellthedata.com/2009/06/python-logistic-regression-with-l2.html
def sigmoid(x):
	return 1.0 / (1.0 + np.exp(-x))
def logisticRegression(y, x, alpha=.1):
	"""A simple logistic regression model with L2 regularization (zero-mean
	Gaussian priors on parameters)."""

	n = y.shape[0]
	betas = np.zeros(x.shape[1])

	# Define the gradient and hand it off to a scipy gradient-based optimizer.

	# Define the derivative of the likelihood with respect to beta_k.
	# Need to multiply by -1 because we will be minimizing.
	def dB_k(B, k):
		return \
		   (k > 0) \
		 * alpha \
		 * B[k] \
		 - np.sum([
			y[i] * x[i, k] * sigmoid(-y[i] * np.dot(B, x[i,:]))
			for i in range(n)])

	# The full gradient is just an array of componentwise derivatives
	def dB(B):
		return \
			np.array([dB_k(B, k)
			for k in range(x.shape[1])])

	# Optimize

	def neg_lik(betas):
		""" Negative likelihood of the data under the current settings of parameters. """
		# Data likelihood
		l = 0
		for i in range(n):
			l += np.log(sigmoid(y[i] * np.dot(betas, x[i,:])))
		# Prior likelihood
		for k in range(1, x.shape[1]):
			l -= (alpha / 2.0) * betas[k]**2
		return -1.0 * l
	betas = fmin_bfgs(neg_lik, betas, fprime=dB)

	# predict the y's again; not sure why sigmoid needs a
	# transformation...
	py = np.zeros(n)
	for i in range(n):
		py[i] = (sigmoid(np.dot(betas, x[i,:])) - .5) * 2

	# f-score
	precision = sum([round(y1)==round(y2) for y1, y2 in zip(y, py) if y2 > 0]) / float(sum([y2>0 for y2 in py]))
	recall = sum([round(y1)==round(y2) for y1, y2 in zip(y, py) if y1 > 0]) / float(sum([y1>0 for y1 in y]))
	f1 = 2 * (precision * recall) / (precision + recall)

	print(precision, recall)

	return betas, f1

def build_vote_matrix(vote):
	voters = [vv for vv in v.voters.all().select_related("option", "person_role")
				if   vv.option.key in ("+", "-")
				 and vv.person_role is not None
				 and vv.person_role.party in ("Democrat", "Republican")
				]

	# what are the predictors?
	beta_labels = ["Intercept", "Party", "Ideology", "Centricity"]

	# ensure scores are loaded
	load_ideology_scores(vote.congress)
	from vote.views import ideology_scores
	def get_ideology_score(voter):
		return ideology_scores[vote.congress].get(voter.person_id,
			ideology_scores[vote.congress].get("MEDIAN:" + voter.person_role.party, 0.0))
	mean_ideology_score = np.mean([ get_ideology_score(voter) for voter in voters ])

	# build x and y vectors
	y = [-1.0 if voter.option.key == "-" else 1.0 for voter in voters]
	x = [
			[
				1.0, # Intercept
				0.0 if voter.person_role.party == "Democrat" else 1.0,
				get_ideology_score(voter),
				1 - 2.0 * abs(mean_ideology_score - get_ideology_score(voter)),
			]
			for voter in voters
		]

	return (np.array(y), np.array(x))

	# debugging with R?
	import csv, sys
	w = csv.writer(sys.stdout)
	w.writerow(['vote'] + beta_labels)
	for i in range(len(y)):
		w.writerow([y[i]] + list(x[i]))

if __name__ == "__main__":
	import sys
	from vote.models import Vote
	v = Vote.objects.get(id=sys.argv[1])
	y, x = build_vote_matrix(v)
	print(logisticRegression(y, x, alpha=.001))
