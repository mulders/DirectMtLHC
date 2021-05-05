import numpy as np
import copy

def writeConfig(outdir,systnames,measurements,merged=[]):
    f = open(outdir+'/mt_config.txt','w')
    f.write('[global]\n\n[end global]\n\n[inputs]\n\n')
    f.write('\tnFiles = {} \n\n'.format(len(measurements)))
    for i, meas in enumerate(measurements):
        f.write('\tfile{} = {}.txt\n'.format(i,meas))
    f.write('\n[end inputs]\n\n[observables]\n\n\tmt_comb = ')
    for meas in measurements:
        f.write('mt_{} '.format(meas))
        if meas!= measurements[-1]: 
            f.write('+ ')
        else: f.write('\n\n[end observables]\n\n')
    f.write('[correlations]\n\n\t#!FILE  =  extra_correlations.txt\n\n[end correlations]\n\n[uncertainty impacts]\n\n')
    for syst in systnames:
        if syst == 'Stat': continue
        if syst in merged: continue
        f.write('\t{} = '.format(syst))
        for meas in measurements:
            f.write('{}_{} '.format(syst,meas))
            if meas != measurements[-1]:
                f.write('+ ')
            else:
                f.write('\n')
    f.write('\n\n[end uncertainty impacts]\n')
    f.close()
    return

def writeMeasurementFile(outdir,systnames,measurement,value,uncert,merged=[]):
    f = open('{}/{}.txt'.format(outdir,measurement),'w')
    f.write('\n\n[hessian]\n\n[end hessian]\n\n[correlation matrix]\n\n[end correlation matrix]\n\n[not fitted]\n\n\t')
    systnames.remove('Stat')
    systnames.append('Stat')
    for syst in systnames:
        if syst == 'Stat':
            f.write('stat ')
        else:
            if syst in merged:
                f.write('{} '.format(syst))
            else:
                f.write('{}_{} '.format(syst,measurement))
    f.write('\n\tmt_{} '.format(measurement))
    for syst in systnames:
        f.write('{} '.format(uncert[measurement][syst]))
    f.write('\n\n[end not fitted]\n\n[systematics]\n\n[end systematics]\n\n[estimates]\n\n')
    f.write('\tn_estimates = 1\n\n')
    f.write('\tname_0 = mt_{}\n'.format(measurement))
    f.write('\tvalue_0 = {}\n'.format(value[measurement]))
    f.write('\n[end estimates]\n')
    f.close()
    return

def writeAllFiles(outdir,systnames,measurements,value,uncert,merged=[]):
    for measurement in measurements:
        writeMeasurementFile(outdir,systnames,measurement,value,uncert,merged)
    return

def writeCorrelations(outdir,systnames,measurements,matrix,merged=[]):
    f = open(outdir+'/extra_correlations.txt','w')
    for syst in systnames:
        if syst == 'Stat': continue
        if syst in merged: continue
        for i, meas_i in enumerate(measurements):
            for j, meas_j in enumerate(measurements):
                if not j>i: continue
                f.write('{}_{} = ({}) {}_{}\n'.format(syst,meas_i,matrix[syst][meas_i][meas_j],syst,meas_j))
        f.write('\n')
    f.close()
    return

def propagateNegativeCorrelations(matrix,systnames,measurements,uncert):
    for syst in systnames:
        if syst == 'Stat': 
            continue
        for meas1 in measurements:
            for meas2 in measurements:
                u1 = uncert[meas1][syst]
                u2 = uncert[meas2][syst]
                if u1 != 0 and u2 != 0:
                    matrix[syst][meas1][meas2] *= u1*u2/abs(u1*u2)
                elif u1 != 0:
                    matrix[syst][meas1][meas2] *= u1/abs(u1)
                elif u2 != 0:
                    matrix[syst][meas1][meas2] *= u2/abs(u2)

    for meas in measurements:
        for syst in systnames:
            if uncert[meas][syst] < 0:
                uncert[meas][syst] *= -1.
    return matrix, uncert

def mergeCorrelations(systnames,measurements,uncert,matrix):

    orig_m = copy.deepcopy(matrix)
    orig_u = copy.deepcopy(uncert)

    ready_s = []
    eligible_s = []

    for syst in systnames:
        if syst == 'Stat': continue
        ready = True
        eligible = True
        for meas1 in measurements:
            for meas2 in measurements:
                if matrix[syst][meas1][meas2] != 1:
                    ready = False
                if abs(matrix[syst][meas1][meas2]) != 1:
                    eligible = False
        if ready:
            ready_s.append(syst)
        elif eligible:
            eligible_s.append(syst)

    ref = measurements[0]
    for syst in eligible_s:
        signs = matrix[syst][ref]
        for meas in measurements:
            uncert[meas][syst] *= signs[meas]
        for m1 in measurements:
            for m2 in measurements:
                matrix[syst][m1][m2] = 1.0
    
    ready_s.extend(eligible_s)

    test_m, test_u = propagateNegativeCorrelations(matrix,systnames,measurements,uncert)

    if test_u != orig_u:
        print 'WARNING: something inconsistent in input uncertainties. Please check'
    
    if test_m != orig_m:
        for syst in systnames:
            if syst == 'Stat': continue
            if not syst in eligible_s: continue
            if test_m[syst] != orig_m[syst]:
                print 'ERROR: correlations for systematic {} inconsistent'.format(syst)

    return ready_s, uncert, matrix


def isInvertible(m):
    try:
        i = np.linalg.inv(m)
    except np.linalg.LinAlgError as err:
        if not 'Singular matrix' in err:
            print 'WARNING', err
        return False
    return True

def isPositiveDefinite(m):
    if not isInvertible(m):
        return False
    w,v = np.linalg.eig(m)
    if (w > 0).all():
      return True
    return False


def getSystMatrix(syst,matrix,measurements,uncert):
    m = np.zeros((len(measurements),len(measurements)))
    for i,meas1 in enumerate(measurements):
        for j,meas2 in enumerate(measurements):
            m[i,j] = matrix[meas1][meas2]*uncert[meas1][syst]*uncert[meas2][syst]
    return m

def getStatMatrix(matrix,measurements,uncert):
    m =  np.zeros((len(measurements),len(measurements)))
    for i,meas in enumerate(measurements):
        m[i,i] = uncert[meas]['Stat']*uncert[meas]['Stat']
    return m

def checkFullMatrix(matrix,systnames,measurements,uncert):

    m_stat = getStatMatrix(matrix,measurements,uncert)
    m_tot = m_stat

    for syst in systnames:
        if syst == 'Stat':
            continue
        m_syst = getSystMatrix(syst,matrix[syst],measurements,uncert)
        m_tot += m_syst

    if isInvertible(m_tot):
        print '\ngood! full matrix is invertible'
    else:
        print '\nERROR! full matrix is not invertible\n'
        return
    if isPositiveDefinite(m_tot):
        print 'good! full matrix is positive definite\n'
    else:
        print 'ERROR: full matrix is not positive definite\n'

    return m_tot
