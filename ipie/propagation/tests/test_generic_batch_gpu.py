import pytest
import numpy
from ipie.utils.misc import dotdict
from ipie.trial_wavefunction.multi_slater import MultiSlater
from ipie.systems.generic import Generic
from ipie.propagation.operations import kinetic_real, kinetic_spin_real_batch
from ipie.propagation.continuous import Continuous
from ipie.propagation.force_bias import construct_force_bias_batch
from ipie.hamiltonians.generic import Generic as HamGeneric
from ipie.legacy.walkers.single_det_batch import SingleDetWalkerBatch
from ipie.legacy.walkers.multi_det_batch import MultiDetTrialWalkerBatch
from ipie.legacy.walkers.single_det import SingleDetWalker
from ipie.legacy.walkers.multi_det import MultiDetWalker
from ipie.utils.testing import (
        generate_hamiltonian,
        get_random_nomsd,
        get_random_phmsd
        )

try:
    import cupy
    no_gpu = not cupy.is_available()
except:
    no_gpu = True

@pytest.mark.unit
@pytest.mark.skipif(no_gpu, reason="gpu not found.")
def test_hybrid_batch():
    numpy.random.seed(7)
    nmo = 10
    nelec = (5,5)
    nwalkers = 10
    nsteps = 25
    h1e, chol, enuc, eri = generate_hamiltonian(nmo, nelec, cplx=False)
    system = Generic(nelec=nelec)
    ham = HamGeneric(h1e=numpy.array([h1e,h1e]),
                     chol=chol.reshape((-1,nmo*nmo)).T.copy(),
                     ecore=0)
    # Test PH type wavefunction.
    wfn, init = get_random_phmsd(system.nup, system.ndown, ham.nbasis, ndet=1, init=True)
    trial = MultiSlater(system, ham, wfn, init=init)
    trial.half_rotate(system, ham)
    trial.psi = trial.psi[0]
    trial.psia = trial.psia[0]
    trial.psib = trial.psib[0]
    trial.calculate_energy(system, ham)

    numpy.random.seed(7)
    cupy.random.seed(7)
    options = {'hybrid': True}
    qmc = dotdict({'dt': 0.005, 'nstblz': 5})
    prop = Continuous(system, ham, trial, qmc, options=options)

    walkers = [SingleDetWalker(system, ham, trial) for iw in range(nwalkers)]
    ovlps = []
    for i in range (nsteps):
        for walker in walkers:
            ovlps += [walker.greens_function(trial)]
            kinetic_real(walker.phi, system, prop.propagator.BH1)
            detR = walker.reortho(trial) # reorthogonalizing to stablize

    numpy.random.seed(7)
    cupy.random.seed(7)

    options = {'hybrid': True}
    qmc = dotdict({'dt': 0.005, 'nstblz': 5, 'batched': True, 'nwalkers': nwalkers})
    prop = Continuous(system, ham, trial, qmc, options=options)
    walker_batch = SingleDetWalkerBatch(system, ham, trial, nwalkers)

    if not no_gpu:
        prop.cast_to_cupy()
        ham.cast_to_cupy()
        trial.cast_to_cupy()
        walker_batch.cast_to_cupy()

    numpy.random.seed(7)
    cupy.random.seed(7)
    ovlps_batch = []
    for i in range (nsteps):
        ovlps_batch += [prop.compute_greens_function(walker_batch, trial)]
        walker_batch.phia = kinetic_spin_real_batch(walker_batch.phia, prop.propagator.BH1[0])
        walker_batch.phib = kinetic_spin_real_batch(walker_batch.phib, prop.propagator.BH1[1])
        walker_batch.reortho()

    phi_batch = cupy.array(walker_batch.phia)
    phi_batch = cupy.asnumpy(phi_batch)

    #assert numpy.allclose(ovlps, cupy.asnumpy(ovlps_batch))

    for iw in range(nwalkers):
        assert numpy.allclose(phi_batch[iw], walkers[iw].phi[:,:system.nup])

    phi_batch = cupy.array(walker_batch.phib)
    phi_batch = cupy.asnumpy(phi_batch)
    for iw in range(nwalkers):
        assert numpy.allclose(phi_batch[iw], walkers[iw].phi[:,system.nup:])

if __name__ == '__main__':
    test_hybrid_batch()