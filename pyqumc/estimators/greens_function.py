import numpy
import scipy.linalg
from pyqumc.utils.linalg import  minor_mask

# Later we will add walker kinds as an input too
def get_greens_function(trial):
    """Wrapper to select the calc_overlap function

    Parameters
    ----------
    trial : class
        Trial wavefunction object.

    Returns
    -------
    propagator : class or None
        Propagator object.
    """

    if trial.name == "MultiSlater" and trial.ndets == 1:
        compute_greens_function = greens_function_single_det
    elif trial.name == "MultiSlater" and trial.ndets > 1 and trial.ortho_expansion == False:
        compute_greens_function = greens_function_multi_det
    elif trial.name == "MultiSlater" and trial.ndets > 1 and trial.ortho_expansion == True:
        compute_greens_function = greens_function_multi_det
        # compute_greens_function = greens_function_multi_det_wicks
    else:
        compute_greens_function = None

    return compute_greens_function

def greens_function(walker_batch, trial):
    if trial.name == "MultiSlater" and trial.ndets == 1:
        return greens_function_single_det(walker_batch, trial)
    elif trial.name == "MultiSlater" and trial.ndets > 1 and trial.ortho_expansion == False:
        return greens_function_multi_det(walker_batch, trial)
    elif trial.name == "MultiSlater" and trial.ndets > 1 and trial.ortho_expansion == True:
        return greens_function_multi_det(walker_batch, trial)
        # return greens_function_multi_det_wicks(walker_batch, trial)
    else:
        return None

def greens_function_single_det(walker_batch, trial):
    """Compute walker's green's function.

    Parameters
    ----------
    walker_batch : object
        SingleDetWalkerBatch object.
    trial : object
        Trial wavefunction object.
    Returns
    -------
    det : float64 / complex128
        Determinant of overlap matrix.
    """
    nup = walker_batch.nup
    ndown = walker_batch.ndown

    det = []

    for iw in range(walker_batch.nwalkers):
        ovlp = numpy.dot(walker_batch.phi[iw][:,:nup].T, trial.psi[:,:nup].conj())
        ovlp_inv = scipy.linalg.inv(ovlp)
        walker_batch.Ghalfa[iw] = numpy.dot(ovlp_inv, walker_batch.phi[iw][:,:nup].T)
        walker_batch.Ga[iw] = numpy.dot(trial.psi[:,:nup].conj(), walker_batch.Ghalfa[iw])
        sign_a, log_ovlp_a = numpy.linalg.slogdet(ovlp)
        sign_b, log_ovlp_b = 1.0, 0.0
        if ndown > 0:
            ovlp = numpy.dot(walker_batch.phi[iw][:,nup:].T, trial.psi[:,nup:].conj())
            sign_b, log_ovlp_b = numpy.linalg.slogdet(ovlp)
            walker_batch.Ghalfb[iw] = numpy.dot(scipy.linalg.inv(ovlp), walker_batch.phi[iw][:,nup:].T)
            walker_batch.Gb[iw] = numpy.dot(trial.psi[:,nup:].conj(), walker_batch.Ghalfb[iw])
        det += [sign_a*sign_b*numpy.exp(log_ovlp_a+log_ovlp_b-walker_batch.log_shift[iw])]
    det = numpy.array(det, dtype=numpy.complex128)

    return det

def greens_function_multi_det(walker_batch, trial):
    """Compute walker's green's function.

    Parameters
    ----------
    walker_batch : object
        MultiDetTrialWalkerBatch object.
    trial : object
        Trial wavefunction object.
    Returns
    -------
    det : float64 / complex128
        Determinant of overlap matrix.
    """
    nup = walker_batch.nup
    walker_batch.Ga.fill(0.0)
    walker_batch.Gb.fill(0.0)
    tot_ovlps = numpy.zeros(walker_batch.nwalkers, dtype = numpy.complex128)
    for iw in range(walker_batch.nwalkers):
        for (ix, detix) in enumerate(trial.psi):
            # construct "local" green's functions for each component of psi_T
            Oup = numpy.dot(walker_batch.phi[iw,:,:nup].T, detix[:,:nup].conj())
            # det(A) = det(A^T)
            sign_a, logdet_a = numpy.linalg.slogdet(Oup)
            walker_batch.det_ovlpas[iw,ix] = sign_a*numpy.exp(logdet_a)
            if abs(walker_batch.det_ovlpas[iw,ix]) < 1e-16:
                continue

            Odn = numpy.dot(walker_batch.phi[iw,:,nup:].T, detix[:,nup:].conj())
            sign_b, logdet_b = numpy.linalg.slogdet(Odn)
            walker_batch.det_ovlpbs[iw,ix] = sign_b*numpy.exp(logdet_b)
            ovlp = walker_batch.det_ovlpas[iw,ix] * walker_batch.det_ovlpbs[iw,ix]
            if abs(ovlp) < 1e-16:
                continue

            inv_ovlp = scipy.linalg.inv(Oup)
            walker_batch.Gihalfa[iw,ix,:,:] = numpy.dot(inv_ovlp, walker_batch.phi[iw][:,:nup].T)
            walker_batch.Gia[iw,ix,:,:] = numpy.dot(detix[:,:nup].conj(), walker_batch.Gihalfa[iw,ix,:,:])

            inv_ovlp = scipy.linalg.inv(Odn)
            walker_batch.Gihalfb[iw,ix,:,:] = numpy.dot(inv_ovlp, walker_batch.phi[iw][:,nup:].T)
            walker_batch.Gib[iw,ix,:,:] = numpy.dot(detix[:,nup:].conj(),walker_batch.Gihalfb[iw,ix,:,:])

            tot_ovlps[iw] += trial.coeffs[ix].conj()*ovlp
            walker_batch.det_weights[iw,ix] = trial.coeffs[ix].conj() * ovlp

            walker_batch.Ga[iw] += walker_batch.Gia[iw,ix,:,:] * walker_batch.det_ovlpas[iw,ix] * trial.coeffs[ix].conj() 
            walker_batch.Gb[iw] += walker_batch.Gib[iw,ix,:,:] * walker_batch.det_ovlpbs[iw,ix] * trial.coeffs[ix].conj()
        
        walker_batch.Ga[iw] /= tot_ovlps[iw]
        walker_batch.Gb[iw] /= tot_ovlps[iw]

    return tot_ovlps

def greens_function_multi_det_wicks(walker_batch, trial):
    """Compute walker's green's function using Wick's theorem.

    Parameters
    ----------
    walker_batch : object
        MultiDetTrialWalkerBatch object.
    trial : object
        Trial wavefunction object.
    Returns
    -------
    det : float64 / complex128
        Determinant of overlap matrix.
    """
    tot_ovlps = numpy.zeros(walker_batch.nwalkers, dtype = numpy.complex128)
    nbasis = walker_batch.Ga.shape[-1]

    nup = walker_batch.nup
    ndown = walker_batch.ndown

    for iw in range(walker_batch.nwalkers):
        walker_batch.Ga[iw].fill(0.0+0.0j)
        walker_batch.Gb[iw].fill(0.0+0.0j)
        
        phi = walker_batch.phi[iw] # walker wfn

        Oalpha = numpy.dot(trial.psi0[:,:nup].conj().T, phi[:,:nup])
        sign_a, logdet_a = numpy.linalg.slogdet(Oalpha)
        logdet_b, sign_b = 0.0, 1.0
        Obeta = numpy.dot(trial.psi0[:,nup:].conj().T, phi[:,nup:])
        sign_b, logdet_b = numpy.linalg.slogdet(Obeta)

        ovlp0 = sign_a*sign_b*numpy.exp(logdet_a+logdet_b)
        ovlpa0 = sign_a*numpy.exp(logdet_a)
        ovlpb0 = sign_b*numpy.exp(logdet_b)

        G0, G0H = gab_spin(trial.psi0, phi, nup, ndown)
        G0a = G0[0]
        G0b = G0[1]
        Q0a = numpy.eye(nbasis) - G0a
        Q0b = numpy.eye(nbasis) - G0b

        ovlp = 0.0 + 0.0j
        ovlp += trial.coeffs[0].conj()
        
        walker_batch.Ga[iw] += G0a * trial.coeffs[0].conj()
        walker_batch.Gb[iw] += G0b * trial.coeffs[0].conj()

        CIa = numpy.zeros((nbasis,nbasis), dtype=numpy.complex128)
        CIb = numpy.zeros((nbasis,nbasis), dtype=numpy.complex128)

        for jdet in range(1, trial.ndets):
            nex_a = len(trial.cre_a[jdet])
            nex_b = len(trial.cre_b[jdet])

            det_a = numpy.zeros((nex_a,nex_a), dtype=numpy.complex128)    
            det_b = numpy.zeros((nex_b,nex_b), dtype=numpy.complex128)    

            for iex in range(nex_a):
                det_a[iex,iex] = G0a[trial.cre_a[jdet][iex],trial.anh_a[jdet][iex]]
                for jex in range(iex+1, nex_a):
                    det_a[iex, jex] = G0a[trial.cre_a[jdet][iex],trial.anh_a[jdet][jex]]
                    det_a[jex, iex] = G0a[trial.cre_a[jdet][jex],trial.anh_a[jdet][iex]]
            for iex in range(nex_b):
                det_b[iex,iex] = G0b[trial.cre_b[jdet][iex],trial.anh_b[jdet][iex]]
                for jex in range(iex+1, nex_b):
                    det_b[iex, jex] = G0b[trial.cre_b[jdet][iex],trial.anh_b[jdet][jex]]
                    det_b[jex, iex] = G0b[trial.cre_b[jdet][jex],trial.anh_b[jdet][iex]]

            ovlpa = numpy.linalg.det(det_a) * trial.phase_a[jdet]
            ovlpb = numpy.linalg.det(det_b) * trial.phase_b[jdet]
            ovlp += trial.coeffs[jdet].conj() * ovlpa * ovlpb

            # contribution 1 (disconnected diagrams)
            walker_batch.Ga[iw] += trial.coeffs[jdet].conj() * G0a * ovlpa 
            walker_batch.Gb[iw] += trial.coeffs[jdet].conj() * G0b * ovlpb 

            # intermediates for contribution 2 (connected diagrams)
            if (nex_a == 1):
                CIa[trial.anh_a[jdet][0],trial.cre_a[jdet][0]] += trial.coeffs[jdet].conj() * trial.phase_a[jdet]
            elif (nex_a == 2):
                p = trial.cre_a[jdet][0]
                q = trial.anh_a[jdet][0]
                r = trial.cre_a[jdet][1]
                s = trial.anh_a[jdet][1]
                CIa[q,p] += trial.coeffs[jdet].conj() * G0a[r,s] * trial.phase_a[jdet]
                CIa[s,r] += trial.coeffs[jdet].conj() * G0a[p,q] * trial.phase_a[jdet]
                CIa[q,r] -= trial.coeffs[jdet].conj() * G0a[p,s] * trial.phase_a[jdet]
                CIa[s,p] -= trial.coeffs[jdet].conj() * G0a[r,q] * trial.phase_a[jdet]
            elif (nex_a == 3):
                p = trial.cre_a[jdet][0]
                q = trial.anh_a[jdet][0]
                r = trial.cre_a[jdet][1]
                s = trial.anh_a[jdet][1]
                t = trial.cre_a[jdet][2]
                u = trial.anh_a[jdet][2]

                CIa[q,p] += trial.coeffs[jdet].conj() * (G0a[r,s]*G0a[t,u] - G0a[r,u]*G0a[t,s]) * trial.phase_a[jdet] # 0 0
                CIa[s,p] -= trial.coeffs[jdet].conj() * (G0a[r,q]*G0a[t,u] - G0a[r,u]*G0a[t,q]) * trial.phase_a[jdet] # 0 1
                CIa[u,p] += trial.coeffs[jdet].conj() * (G0a[r,q]*G0a[t,s] - G0a[r,s]*G0a[t,q]) * trial.phase_a[jdet] # 0 2
                
                CIa[q,r] -= trial.coeffs[jdet].conj() * (G0a[p,s]*G0a[t,u] - G0a[p,u]*G0a[t,s]) * trial.phase_a[jdet] # 1 0
                CIa[s,r] += trial.coeffs[jdet].conj() * (G0a[p,q]*G0a[t,u] - G0a[p,u]*G0a[t,q]) * trial.phase_a[jdet] # 1 1
                CIa[u,r] -= trial.coeffs[jdet].conj() * (G0a[p,q]*G0a[t,s] - G0a[p,s]*G0a[t,q]) * trial.phase_a[jdet] # 1 2

                CIa[q,t] += trial.coeffs[jdet].conj() * (G0a[p,s]*G0a[r,u] - G0a[p,u]*G0a[r,s]) * trial.phase_a[jdet] # 2 0
                CIa[s,t] -= trial.coeffs[jdet].conj() * (G0a[p,q]*G0a[r,u] - G0a[p,u]*G0a[r,q]) * trial.phase_a[jdet] # 2 1
                CIa[u,t] += trial.coeffs[jdet].conj() * (G0a[p,q]*G0a[r,s] - G0a[p,s]*G0a[r,q]) * trial.phase_a[jdet] # 2 2

            elif (nex_a > 3):
                cofactor = numpy.zeros((nex_a-1, nex_a-1), dtype=numpy.complex128)
                for iex in range(nex_a):
                    p = trial.cre_a[jdet][iex]
                    for jex in range(nex_a):
                        q = trial.anh_a[jdet][jex]
                        cofactor[:,:] = minor_mask(det_b, iex, jex)
                        CIa[q,p] += trial.coeffs[jdet].conj() * numpy.linalg.det(cofactor) * trial.phase_a[jdet] * (-1)**(iex+jex)

            if (nex_b == 1):
                CIb[trial.anh_b[jdet][0],trial.cre_b[jdet][0]] += trial.coeffs[jdet].conj() * trial.phase_b[jdet]
            elif (nex_b == 2):
                p = trial.cre_b[jdet][0]
                q = trial.anh_b[jdet][0]
                r = trial.cre_b[jdet][1]
                s = trial.anh_b[jdet][1]
                CIb[q,p] += trial.coeffs[jdet].conj() * G0b[r,s] * trial.phase_b[jdet]
                CIb[s,r] += trial.coeffs[jdet].conj() * G0b[p,q] * trial.phase_b[jdet]
                CIb[q,r] -= trial.coeffs[jdet].conj() * G0b[p,s] * trial.phase_b[jdet]
                CIb[s,p] -= trial.coeffs[jdet].conj() * G0b[r,q] * trial.phase_b[jdet]
            elif (nex_b == 3):
                p = trial.cre_b[jdet][0]
                q = trial.anh_b[jdet][0]
                r = trial.cre_b[jdet][1]
                s = trial.anh_b[jdet][1]
                t = trial.cre_b[jdet][2]
                u = trial.anh_b[jdet][2]

                CIb[q,p] += trial.coeffs[jdet].conj() * (G0b[r,s]*G0b[t,u] - G0b[r,u]*G0b[t,s]) * trial.phase_b[jdet] # 0 0
                CIb[s,p] -= trial.coeffs[jdet].conj() * (G0b[r,q]*G0b[t,u] - G0b[r,u]*G0b[t,q]) * trial.phase_b[jdet] # 0 1
                CIb[u,p] += trial.coeffs[jdet].conj() * (G0b[r,q]*G0b[t,s] - G0b[r,s]*G0b[t,q]) * trial.phase_b[jdet] # 0 2
                
                CIb[q,r] -= trial.coeffs[jdet].conj() * (G0b[p,s]*G0b[t,u] - G0b[p,u]*G0b[t,s]) * trial.phase_b[jdet] # 1 0
                CIb[s,r] += trial.coeffs[jdet].conj() * (G0b[p,q]*G0b[t,u] - G0b[p,u]*G0b[t,q]) * trial.phase_b[jdet] # 1 1
                CIb[u,r] -= trial.coeffs[jdet].conj() * (G0b[p,q]*G0b[t,s] - G0b[p,s]*G0b[t,q]) * trial.phase_b[jdet] # 1 2

                CIb[q,t] += trial.coeffs[jdet].conj() * (G0b[p,s]*G0b[r,u] - G0b[p,u]*G0b[r,s]) * trial.phase_b[jdet] # 2 0
                CIb[s,t] -= trial.coeffs[jdet].conj() * (G0b[p,q]*G0b[r,u] - G0b[p,u]*G0b[r,q]) * trial.phase_b[jdet] # 2 1
                CIb[u,t] += trial.coeffs[jdet].conj() * (G0b[p,q]*G0b[r,s] - G0b[p,s]*G0b[r,q]) * trial.phase_b[jdet] # 2 2

            elif (nex_b > 3):
                cofactor = numpy.zeros((nex_b-1, nex_b-1), dtype=numpy.complex128)
                for iex in range(nex_b):
                    p = trial.cre_b[jdet][iex]
                    for jex in range(nex_b):
                        q = trial.anh_b[jdet][jex]
                        cofactor[:,:] = minor_mask(det_b, iex, jex)
                        CIb[q,p] += trial.coeffs[jdet].conj() * numpy.linalg.det(cofactor) * trial.phase_b[jdet] * (-1)**(iex+jex)        

        # contribution 2 (connected diagrams)
        walker_batch.Ga[iw] += Q0a.dot(CIa).dot(G0a)
        walker_batch.Gb[iw] += Q0b.dot(CIb).dot(G0b)
        
        ovlp *= ovlp0

        walker_batch.Ga[iw] *= ovlpa0
        walker_batch.Gb[iw] *= ovlpb0

        walker_batch.Ga[iw] /= ovlp
        walker_batch.Gb[iw] /= ovlp

        tot_ovlps[iw] = ovlp

    return tot_ovlps

# Green's functions
def gab(A, B):
    r"""One-particle Green's function.

    This actually returns 1-G since it's more useful, i.e.,

    .. math::
        \langle \phi_A|c_i^{\dagger}c_j|\phi_B\rangle =
        [B(A^{\dagger}B)^{-1}A^{\dagger}]_{ji}

    where :math:`A,B` are the matrices representing the Slater determinants
    :math:`|\psi_{A,B}\rangle`.

    For example, usually A would represent (an element of) the trial wavefunction.

    .. warning::
        Assumes A and B are not orthogonal.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Matrix representation of the bra used to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.

    Returns
    -------
    GAB : :class:`numpy.ndarray`
        (One minus) the green's function.
    """
    # Todo: check energy evaluation at later point, i.e., if this needs to be
    # transposed. Shouldn't matter for Hubbard model.
    inv_O = scipy.linalg.inv((A.conj().T).dot(B))
    GAB = B.dot(inv_O.dot(A.conj().T))
    return GAB


def gab_mod(A, B):
    r"""One-particle Green's function.

    This actually returns 1-G since it's more useful, i.e.,

    .. math::
        \langle \phi_A|c_i^{\dagger}c_j|\phi_B\rangle =
        [B(A^{\dagger}B)^{-1}A^{\dagger}]_{ji}

    where :math:`A,B` are the matrices representing the Slater determinants
    :math:`|\psi_{A,B}\rangle`.

    For example, usually A would represent (an element of) the trial wavefunction.

    .. warning::
        Assumes A and B are not orthogonal.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Matrix representation of the bra used to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.

    Returns
    -------
    GAB : :class:`numpy.ndarray`
        (One minus) the green's function.
    """
    O = numpy.dot(B.T, A.conj())
    GHalf = numpy.dot(scipy.linalg.inv(O), B.T)
    G = numpy.dot(A.conj(), GHalf)
    return (G, GHalf)

def gab_spin(A, B, na, nb):
    GA, GAH = gab_mod(A[:,:na],B[:,:na])
    if nb > 0:
        GB, GBH = gab_mod(A[:,na:],B[:,na:])
    return numpy.array([GA, GB]), [GAH, GBH]


def gab_mod_ovlp(A, B):
    r"""One-particle Green's function.

    This actually returns 1-G since it's more useful, i.e.,

    .. math::
        \langle \phi_A|c_i^{\dagger}c_j|\phi_B\rangle =
        [B(A^{\dagger}B)^{-1}A^{\dagger}]_{ji}

    where :math:`A,B` are the matrices representing the Slater determinants
    :math:`|\psi_{A,B}\rangle`.

    For example, usually A would represent (an element of) the trial wavefunction.

    .. warning::
        Assumes A and B are not orthogonal.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Matrix representation of the bra used to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.

    Returns
    -------
    GAB : :class:`numpy.ndarray`
        (One minus) the green's function.
    """
    inv_O = scipy.linalg.inv(numpy.dot(B.T, A.conj()))
    GHalf = numpy.dot(inv_O, B.T)
    G = numpy.dot(A.conj(), GHalf)
    return (G, GHalf, inv_O)


def gab_multi_det(A, B, coeffs):
    r"""One-particle Green's function.

    This actually returns 1-G since it's more useful, i.e.,

    .. math::
        \langle \phi_A|c_i^{\dagger}c_j|\phi_B\rangle = [B(A^{*T}B)^{-1}A^{*T}]_{ji}

    where :math:`A,B` are the matrices representing the Slater determinants
    :math:`|\psi_{A,B}\rangle`.

    For example, usually A would represent a multi-determinant trial wavefunction.

    .. warning::
        Assumes A and B are not orthogonal.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Numpy array of the Matrix representation of the elements of the bra used
        to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.
    coeffs: :class:`numpy.ndarray`
        Trial wavefunction expansion coefficients. Assumed to be complex
        conjugated.

    Returns
    -------
    GAB : :class:`numpy.ndarray`
        (One minus) the green's function.
    """
    # Todo: check energy evaluation at later point, i.e., if this needs to be
    # transposed. Shouldn't matter for Hubbard model.
    Gi = numpy.zeros(A.shape)
    overlaps = numpy.zeros(A.shape[1])
    for (ix, Aix) in enumerate(A):
        # construct "local" green's functions for each component of A
        # Todo: list comprehension here.
        inv_O = scipy.linalg.inv((Aix.conj().T).dot(B))
        Gi[ix] = (B.dot(inv_O.dot(Aix.conj().T))).T
        overlaps[ix] = 1.0 / scipy.linalg.det(inv_O)
    denom = numpy.dot(coeffs, overlaps)
    return numpy.einsum('i,ijk,i->jk', coeffs, Gi, overlaps) / denom


def gab_multi_ghf_full(A, B, coeffs, bp_weights):
    """Green's function for back propagation.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Numpy array of the Matrix representation of the elements of the bra used
        to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.
    coeffs: :class:`numpy.ndarray`
        Trial wavefunction expansion coefficients. Assumed to be complex
        conjugated.
    bp_weights : :class:`numpy.ndarray`
        Factors arising from GS orthogonalisation.

    Returns
    -------
    G : :class:`numpy.ndarray`
        (One minus) the green's function.
    """
    M = A.shape[1] // 2
    Gi, overlaps = construct_multi_ghf_gab(A, B, coeffs)
    scale = max(max(bp_weights), max(overlaps))
    full_weights = bp_weights * coeffs * overlaps / scale
    denom = sum(full_weights)
    G = numpy.einsum('i,ijk->jk', full_weights, Gi) / denom

    return G


def gab_multi_ghf(A, B, coeffs, Gi=None, overlaps=None):
    """Construct components of multi-ghf trial wavefunction.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Numpy array of the Matrix representation of the elements of the bra used
        to construct G.
    B : :class:`numpy.ndarray`
        Matrix representation of the ket used to construct G.
    Gi : :class:`numpy.ndarray`
        Array to store components of G. Default: None.
    overlaps : :class:`numpy.ndarray`
        Array to overlaps. Default: None.

    Returns
    -------
    Gi : :class:`numpy.ndarray`
        Array to store components of G. Default: None.
    overlaps : :class:`numpy.ndarray`
        Array to overlaps. Default: None.
    """
    M = B.shape[0] // 2
    if Gi is None:
        Gi = numpy.zeros(shape=(A.shape[0],A.shape[1],A.shape[1]), dtype=A.dtype)
    if overlaps is None:
        overlaps = numpy.zeros(A.shape[0], dtype=A.dtype)
    for (ix, Aix) in enumerate(A):
        # construct "local" green's functions for each component of A
        # Todo: list comprehension here.
        inv_O = scipy.linalg.inv((Aix.conj().T).dot(B))
        Gi[ix] = (B.dot(inv_O.dot(Aix.conj().T)))
        overlaps[ix] = 1.0 / scipy.linalg.det(inv_O)
    return (Gi, overlaps)


def gab_multi_det_full(A, B, coeffsA, coeffsB, GAB, weights):
    r"""One-particle Green's function.

    This actually returns 1-G since it's more useful, i.e.,

    .. math::
        \langle \phi_A|c_i^{\dagger}c_j|\phi_B\rangle = [B(A^{*T}B)^{-1}A^{*T}]_{ji}

    where :math:`A,B` are the matrices representing the Slater determinants
    :math:`|\psi_{A,B}\rangle`.

    .. todo: Fix docstring

    Here we assume both A and B are multi-determinant expansions.

    .. warning::
        Assumes A and B are not orthogonal.

    Parameters
    ----------
    A : :class:`numpy.ndarray`
        Numpy array of the Matrix representation of the elements of the bra used
        to construct G.
    B : :class:`numpy.ndarray`
        Array containing elements of multi-determinant matrix representation of
        the ket used to construct G.
    coeffsA: :class:`numpy.ndarray`
        Trial wavefunction expansion coefficients for wavefunction A. Assumed to
        be complex conjugated.
    coeffsB: :class:`numpy.ndarray`
        Trial wavefunction expansion coefficients for wavefunction A. Assumed to
        be complex conjugated.
    GAB : :class:`numpy.ndarray`
        Matrix of Green's functions.
    weights : :class:`numpy.ndarray`
        Matrix of weights needed to construct G

    Returns
    -------
    G : :class:`numpy.ndarray`
        Full Green's function.
    """
    for ix, (Aix, cix) in enumerate(zip(A, coeffsA)):
        for iy, (Biy, ciy) in enumerate(zip(B, coeffsB)):
            # construct "local" green's functions for each component of A
            inv_O = scipy.linalg.inv((Aix.conj().T).dot(Biy))
            GAB[ix,iy] = (Biy.dot(inv_O)).dot(Aix.conj().T)
            GAB[ix,iy] = (Biy.dot(inv_O)).dot(Aix.conj().T)
            weights[ix,iy] =  cix*(ciy.conj()) / scipy.linalg.det(inv_O)
    denom = numpy.sum(weights)
    G = numpy.einsum('ij,ijkl->kl', weights, GAB) / denom
    return G
