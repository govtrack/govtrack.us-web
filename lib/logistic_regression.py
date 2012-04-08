"""
 Python module for computing Logistic Regression.
 Requires numpy, matplotlib

 Version: 20090622+JT0
 
 Modified by Joshua Tauberer to use numpy.linalg.lstsq rather than inv
 to avoid problems with singular matrices, and use vstack rather than
 assignment to an array slice for clarity.

 Contact:  Jeffrey Whitaker <jeffrey.s.whitaker@noaa.gov>

 copyright (c) by Jeffrey Whitaker.
 
 Permission to use, copy, modify, and distribute this software and its
 documentation for any purpose and without fee is hereby granted,
 provided that the above copyright notice appear in all copies and that
 both the copyright notice and this permission notice appear in
 supporting documentation.
 THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
 INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO
 EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, INDIRECT OR
 CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF
 USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
 OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
 PERFORMANCE OF THIS SOFTWARE.

"""

import numpy as np

def simple_logistic_regression(x,y,beta_start=None,verbose=False,
                               CONV_THRESH=1.e-3,MAXIT=500):
    """
 Uses the Newton-Raphson algorithm to calculate maximum
 likliehood estimates of a simple logistic regression.  

 Faster than logistic_regression when there is only one predictor.

 x - predictor
 y - binary outcomes (len(y) = len(x))
 beta_start - initial beta (default zero)
 if verbose=True, diagnostics printed for each iteration.
 MAXIT - max number of iterations (default 500)
 CONV_THRESH - convergence threshold (sum of absolute differences
  of beta-beta_old)

 returns beta (the logistic regression coefficients, a 2-element vector),
 J_bar (the 2x2 information matrix), and l (the log-likeliehood).
 J_bar can be used to estimate the covariance matrix and the standard
 error beta.
 l can be used for a chi-squared significance test.

 covmat = inverse(J_bar)     --> covariance matrix
 stderr = sqrt(diag(covmat)) --> standard errors for beta
 deviance = -2l              --> scaled deviance statistic
 chi-squared value for -2l is the model chi-squared test.
    """
    if len(x) != len(y):
        raise ValueError, "x and y should be the same length!"
    if beta_start is None:
        beta_start = np.zeros(2,x.dtype)
    iter = 0; diff = 1.; beta = beta_start  # initial values
    if verbose:
        print 'iteration  beta log-likliehood |beta-beta_old|' 
    while iter < MAXIT:
        beta_old = beta 
        p = np.exp(beta[0]+beta[1]*x)/(1.+np.exp(beta[0]+beta[1]*x))
        l = np.sum(y*np.log(p) + (1.-y)*np.log(1.-p)) # log-likliehood
        s = np.array([np.sum(y-p), np.sum((y-p)*x)])  # scoring function
        # information matrix
        J_bar = np.array([[np.sum(p*(1-p)),np.sum(p*(1-p)*x)],
                          [np.sum(p*(1-p)*x),np.sum(p*(1-p)*x*x)]])
        #beta = beta_old + np.dot(np.linalg.inv(J_bar),s)  # new value of beta
        beta = beta_old + np.linalg.lstsq(J_bar, s)[0]  # new value of beta
        # sum of absolute differences
        diff = np.sum(np.fabs(beta-beta_old))
        if verbose:
            print iter+1, beta, l, diff
        if diff <= CONV_THRESH: break
        iter = iter + 1
    return beta, J_bar, l

def logistic_regression(x,y,beta_start=None,verbose=False,CONV_THRESH=1.e-3,
                        MAXIT=500):
    """
 Uses the Newton-Raphson algorithm to calculate maximum
 likliehood estimates of a logistic regression.

 Can handle multivariate case (more than one predictor).

 x - 2-d array of predictors. Number of predictors = x.shape[0]=N
 y - binary outcomes (len(y) = x.shape[1])
 beta_start - initial beta vector (default zeros(N+1,x.dtype)
 if verbose=True, diagnostics printed for each iteration.
 MAXIT - max number of iterations (default 500)
 CONV_THRESH - convergence threshold (sum of absolute differences
  of beta-beta_old)

 returns beta (the logistic regression coefficients, a N+1 element vector),
 J_bar (the (N+1)x(N=1) information matrix), and l (the log-likeliehood).
 J_bar can be used to estimate the covariance matrix and the standard
 error beta.
 l can be used for a chi-squared significance test.

 covmat = inverse(J_bar)     --> covariance matrix
 stderr = sqrt(diag(covmat)) --> standard errors for beta
 deviance = -2l              --> scaled deviance statistic
 chi-squared value for -2l is the model chi-squared test.
    """
    if x.shape[-1] != len(y):
        raise ValueError, "x.shape[-1] and y should be the same length!"
    try:
        N, npreds = x.shape[1], x.shape[0]
    except: # single predictor, use simple logistic regression routine.
        N, npreds = x.shape[-1], 1
        return simple_logistic_regression(x,y,beta_start=beta_start,
               CONV_THRESH=CONV_THRESH,MAXIT=MAXIT,verbose=verbose)
    if beta_start is None:
        beta_start = np.zeros(npreds+1,x.dtype)
    X = np.vstack((np.ones((1,N), x.dtype), x))
    Xt = np.transpose(X)
    iter = 0; diff = 1.; beta = beta_start  # initial values
    if verbose:
        print 'iteration  beta log-likliehood |beta-beta_old|' 
    while iter < MAXIT:
        beta_old = beta 
        ebx = np.exp(np.dot(beta, X))
        p = ebx/(1.+ebx)
        l = np.sum(y*np.log(p) + (1.-y)*np.log(1.-p)) # log-likeliehood
        s = np.dot(X, y-p)                            # scoring function
        J_bar = np.dot(X*np.multiply(p,1.-p),Xt)      # information matrix
        #beta = beta_old + np.dot(np.linalg.inv(J_bar),s) # new value of beta
        beta = beta_old + np.linalg.lstsq(J_bar, s)[0] # new value of beta
        diff = np.sum(np.fabs(beta-beta_old)) # sum of absolute differences
        if verbose:
            print iter+1, beta, l, diff
        if diff <= CONV_THRESH: break
        iter = iter + 1
    if iter == MAXIT and diff > CONV_THRESH: 
        print 'warning: convergence not achieved with threshold of %s in %s iterations' % (CONV_THRESH,MAXIT)
    return beta, J_bar, l

def calcprob(beta, x):
    """
 calculate probabilities (in percent) given beta and x
    """
    try:
        N, npreds = x.shape[1], x.shape[0]
    except: # single predictor, x is a vector, len(beta)=2.
        N, npreds = len(x), 1
	print len(beta), npreds
    if len(beta) != npreds+1:
        raise ValueError,'sizes of beta and x do not match!'
    if npreds==1: # simple logistic regression
        return 100.*np.exp(beta[0]+beta[1]*x)/(1.+np.exp(beta[0]+beta[1]*x))
    X = np.ones((npreds+1,N), x.dtype)
    X[1:, :] = x
    ebx = np.exp(np.dot(beta, X))
    return 100.*ebx/(1.+ebx)

if __name__ == '__main__':
    from numpy.random import multivariate_normal
    # number of realizations.
    nsamps = 100000
    # correlations
    r12 = 0.5 
    r13 = 0.25
    r23 = 0.125 # correlation between predictors.
    # random draws from trivariate normal distribution
    x = multivariate_normal(np.array([0,0,0]),np.array([[1,r12,r13],[r12,1,r23],[r13,r23,1]]), nsamps)
    x2 = multivariate_normal(np.array([0,0,0]),np.array([[1,r12,r13],[r12,1,r23],[r13,r23,1]]), nsamps)
    print
    print 'correlations (r12,r13,r23) = ',r12,r13,r23
    print 'number of realizations = ',nsamps
    # training data.
    truth = x[:,0]
    thresh = 0. # forecast threshold (0 is climatology)
    climprob = np.sum((truth > thresh).astype('f'))/nsamps
    fcst = np.transpose(x[:,1:]) # 2 predictors.
    # independent data for verification.
    truth2 = x2[:,0]
    fcst2 = np.transpose(x2[:,1:])
    # compute logistic regression.
    obs_binary = truth > thresh
    # using only 1st predictor.
    beta,Jbar,llik = logistic_regression(fcst[0,:],obs_binary,verbose=True)
    covmat = np.linalg.inv(Jbar)
    stderr = np.sqrt(np.diag(covmat))
    print 'using only first predictor:'
    print 'beta =' ,beta
    print 'standard error =',stderr
    # forecasts from independent data.
    prob = calcprob(beta, fcst2[0,:])
    # compute Brier Skill Score
    verif = (truth2 > thresh).astype('f')
    bs = np.mean((0.01*prob - verif)**2)
    bsclim = np.mean((climprob - verif)**2)
    bss = 1.-(bs/bsclim)
    print 'Brier Skill Score = ',bss
    # using only 2nd predictor.
    beta,Jbar,llik = logistic_regression(fcst[1,:],obs_binary,verbose=True)
    covmat = np.linalg.inv(Jbar)
    stderr = np.sqrt(np.diag(covmat))
    print 'using only second predictor:'
    print 'beta =' ,beta
    print 'standard error =',stderr
    # forecasts from independent data.
    prob = calcprob(beta, fcst2[1,:])
    # compute Brier Skill Score
    verif = (truth2 > thresh).astype('f')
    bs = np.mean((0.01*prob - verif)**2)
    bsclim = np.mean((climprob - verif)**2)
    bss = 1.-(bs/bsclim)
    print 'Brier Skill Score = ',bss
    # using both predictors.
    beta,Jbar,llik = logistic_regression(fcst,obs_binary,verbose=True)
    covmat = np.linalg.inv(Jbar)
    stderr = np.sqrt(np.diag(covmat))
    print 'using both predictors:'
    print 'beta =' ,beta
    print 'standard error =',stderr
    # forecasts from independent data.
    prob = calcprob(beta, fcst2)
    # compute Brier Skill Score
    verif = (truth2 > thresh).astype('f')
    bs = np.mean((0.01*prob - verif)**2)
    bsclim = np.mean((climprob - verif)**2)
    bss = 1.-(bs/bsclim)
    print 'Brier Skill Score = ',bss
    print """\n
If Brier Skill Scores within +/- 0.01 of 0.16, 0.04 and 0.18 everything OK\n"""
# calculate reliability.
    print 'reliability:'
    totfreq = np.zeros(10,'f')
    obfreq = np.zeros(10,'f')
    for icat in range(10):
        prob1 = icat*10.
        prob2 = (icat+1)*10.
        test1 = prob > prob1
        test2 = prob <= prob2
        testf = 1.0*test1*test2
        testfv = verif*testf 
        totfreq[icat] = np.sum(testf)
        obfreq[icat] = np.sum(testfv)
    fcstprob = np.zeros(10,'f')
    reliability = np.zeros(10,'f')
    frequse = np.zeros(10,'f')
    totsum = nsamps
    print 'fcst prob, obs frequency, frequency of use'
    for icat in range(10):
        prob1 = icat*10.
        prob2 = (icat+1)*10.
        fcstprob[icat] = 0.5*(prob1+prob2)
        reliability[icat] = 100.*obfreq[icat]/totfreq[icat]
        frequse[icat] = 100.*totfreq[icat]/totsum
        print fcstprob[icat],reliability[icat],frequse[icat]
    # make a reliability diagram
    print 'plotting reliability diagram...'
    import matplotlib.pyplot as plt
    fig=plt.figure(figsize=(8,7))
    ax = fig.add_axes([0.1,0.1,0.8,0.8])
    plt.plot(fcstprob,reliability,'bo-')
    plt.plot(np.arange(0,110,10),np.arange(0,110,10),'r--')
    plt.xlabel('forecast probability')
    plt.ylabel('observed frequency')
    plt.title('Reliability Diagram')
    plt.text(75,15,'BSS = %4.2f' % bss,fontsize=14)
    ax = plt.axes([.25, .6, .2, .2], axisbg='y')
    plt.bar(10*np.arange(10), frequse, width=10)
    plt.xlabel('forecast probability')
    plt.ylabel('percent issued')
    plt.title('Frequency of Use')
    plt.show()
