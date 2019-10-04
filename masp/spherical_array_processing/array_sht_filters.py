# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
# Copyright (c) 2019, Eurecat / UPF
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the <organization> nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   @file   array_sht_filters.py
#   @author Andrés Pérez-López
#   @date   02/10/2019
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import numpy as np
import warnings
from masp.utils import c, C, elev2incl, get_sh, replicate_per_order
from masp.array_response_simulator import sph_modal_coefs
from masp.validate_data_types import _validate_int, _validate_float, _validate_ndarray_2D


def array_sht_filters_theory_radInverse(R, nMic, order_sht, Lfilt, fs, amp_threshold):
    """
    Generate SHT filters based on theoretical responses (regularized radial inversion)

    Parameters
    ----------
    R : float
        Microphone array radius, in meter.
    nMic : int
        Number of microphone capsules.
    order_sht : int
        Spherical harmonic transform order.
    Lfilt : int
        Number of FFT points for the output filters. It must be even.
    fs : int
        Sample rate for the output filters.
    amp_threshold : float
         Max allowed amplification for filters, in dB.

    Returns
    -------
    h_filt : ndarray
        Impulse responses of the filters. Dimension = (Lfilt, order_sht+1).
    H_filt: ndarray
        Frequency-domain filters. Dimension = (Lfilt//2+1, order_sht+1).

    Raises
    -----
    TypeError, ValueError: if method arguments mismatch in type, dimension or value.
    UserWarning: if `nMic` not big enough for the required sht order.

    Notes
    -----
    Generate the filters to convert microphone signals from a spherical
    microphone array to SH signals, based on an ideal theoretical model of
    the array. The filters are generated from an inversion of the radial
    components of the response, neglecting spatial aliasing effects and
    non-ideal arrangements of the microphones. One filter is shared by all
    SH signals of the same order in this case.
    Here this single channel inversion problem is done with a constraint on
    max allowed amplification regularization, using Tikhonov
    regularization, similar e.g. to:

        Moreau, S., Daniel, J., Bertet, S., 2006,
        3D sound field recording with higher order ambisonics-objective
        measurements and validation of spherical microphone.
        In Audio Engineering Society Convention 120.

    """

    _validate_float('R', R, positive=True)
    _validate_int('nMic', nMic, positive=True)
    _validate_int('order_sht', order_sht, positive=True)
    _validate_int('Lfilt', Lfilt, positive=True, parity='even')
    _validate_int('fs', fs, positive=True)
    _validate_float('amp_threshold', amp_threshold)

    f = np.arange(Lfilt // 2 + 1) * fs / Lfilt

    # Adequate sht order to the number of microphones
    if order_sht > np.sqrt(nMic) - 1:
        order_sht = int(np.floor(np.sqrt(nMic) - 1))
        warnings.warn("Set order too high for the number of microphones, should be N<=np.sqrt(Q)-1. Auto set to "+str(order_sht), UserWarning)

    # Modal responses
    kR = 2 * np.pi * f * R / c
    bN = sph_modal_coefs(order_sht, kR, 'rigid') / (4 * np.pi)

    # Encoding matrix with regularization
    a_dB = amp_threshold
    alpha = complex(np.sqrt(nMic) * np.power(10, a_dB / 20))  # Explicit casting to allow negative sqrt (a_dB < 0)
    beta = np.sqrt((1 - np.sqrt(1 - 1 / np.power(alpha,2))) / (1 + np.sqrt(1 - 1 / np.power(alpha,2))))  # Moreau & Daniel
    # Regularized single channel equalization filters per order
    H_filt = (bN).conj() / (np.power(np.abs(bN), 2) + np.power(beta, 2) * np.ones((Lfilt // 2 + 1, order_sht + 1)))

    # Time domain filters
    temp = H_filt.copy()
    temp[-1,:] = np.real(temp[-1,:])
    # Create the symmetric conjugate negative frequency response for a real time-domain signal
    h_filt = np.real(np.fft.fftshift(np.fft.ifft(np.append(temp, np.conj(temp[-2:0:-1,:]), axis=0), axis=0), axes=0))

    # TODO: check return ordering
    return h_filt, H_filt


def array_sht_filters_theory_softLim(R, nMic, order_sht, Lfilt, fs, amp_threshold):
    """
    Generate SHT filters based on theoretical responses (soft-limiting)

    Parameters
    ----------
    R : float
        Microphone array radius, in meter.
    nMic : int
        Number of microphone capsules.
    order_sht : int
        Spherical harmonic transform order.
    Lfilt : int
        Number of FFT points for the output filters. It must be even.
    fs : int
        Sample rate for the output filters.
    amp_threshold : float
         Max allowed amplification for filters, in dB.

    Returns
    -------
    h_filt : ndarray
        Impulse responses of the filters. Dimension = (Lfilt, order_sht+1).
    H_filt: ndarray
        Frequency-domain filters. Dimension = (Lfilt//2+1, order_sht+1).

    Raises
    -----
    TypeError, ValueError: if method arguments mismatch in type, dimension or value.
    UserWarning: if `nMic` not big enough for the required sht order.

    Notes
    -----
    Generate the filters to convert microphone signals from a spherical
    microphone array to SH signals, based on an ideal theoretical model of
    the array. The filters are generated from an inversion of the radial
    components of the response, neglecting spatial aliasing effects and
    non-ideal arrangements of the microphones. One filter is shared by all
    SH signals of the same order in this case.
    Here this single channel inversion problem is done through a
    thresholding approach on the inversion, limited to a max allowed
    amplification. The limiting follows the approach of

        Bernschutz, B., Porschmann, C., Spors, S., Weinzierl, S., Versterkung, B., 2011.
        Soft-limiting der modalen amplitudenverst?rkung bei sph?rischen mikrofonarrays im plane wave decomposition verfahren.
        Proceedings of the 37. Deutsche Jahrestagung fur Akustik (DAGA 2011)

    """

    _validate_float('R', R, positive=True)
    _validate_int('nMic', nMic, positive=True)
    _validate_int('order_sht', order_sht, positive=True)
    _validate_int('Lfilt', Lfilt, positive=True, parity='even')
    _validate_int('fs', fs, positive=True)
    _validate_float('amp_threshold', amp_threshold)

    f = np.arange(Lfilt // 2 + 1) * fs / Lfilt

    # Adequate sht order to the number of microphones
    if order_sht > np.sqrt(nMic) - 1:
        order_sht = int(np.floor(np.sqrt(nMic) - 1))
        warnings.warn("Set order too high for the number of microphones, should be N<=np.sqrt(Q)-1. Auto set to "+str(order_sht), UserWarning)

    # Modal responses
    kR = 2 * np.pi * f * R / c
    bN = sph_modal_coefs(order_sht, kR, 'rigid') / (4 * np.pi)  # due to modified SHs, the 4pi term disappears from the plane wave expansion
    # Single channel equalization filters per order
    inv_bN = 1. / bN
    inv_bN[0, 1:] = 0.

    # Encoding matrix with regularization
    a_dB = amp_threshold
    alpha = complex(np.sqrt(nMic) * np.power(10, a_dB / 20))  # Explicit casting to allow negative sqrt (a_dB < 0)
    # Regularized single channel equalization filters per order
    H_filt = (2*alpha/np.pi) * (np.abs(bN) * inv_bN) * np.arctan((np.pi / (2 * alpha))* np.abs(inv_bN))

    # Time domain filters
    temp = H_filt.copy()
    temp[-1,:] = np.real(temp[-1,:])
    # Create the symmetric conjugate negative frequency response for a real time-domain signal
    h_filt = np.real(np.fft.fftshift(np.fft.ifft(np.append(temp, np.conj(temp[-2:0:-1,:]), axis=0), axis=0), axes=0))

    # TODO: check return order
    return h_filt, H_filt


def array_sht_filters_theory_regLS(R, mic_dirsAziElev, order_sht, Lfilt, fs, amp_threshold):
    """
    Generate SHT filters based on theoretical responses (regularized least-squares)

    Parameters
    ----------
    R : float
        Microphone array radius, in meter.
    mic_dirsAziElev : ndarray
        Evaluation directions. Dimension = (nDirs, 2).
        Directions are expected in radians, expressed in pairs [azimuth, elevation].
    order_sht : int
        Spherical harmonic transform order.
    Lfilt : int
        Number of FFT points for the output filters. It must be even.
    fs : int
        Sample rate for the output filters.
    amp_threshold : float
         Max allowed amplification for filters, in dB.

    Returns
    -------
    h_filt : ndarray
        Impulse responses of the filters. Dimension = ( nMic, (order_sht+1)^2, Lfilt ).
    H_filt: ndarray
        Frequency-domain filters. Dimension = ( nMic, (order_sht+1)^2, Lfilt//2+1 ).

    Raises
    -----
    TypeError, ValueError: if method arguments mismatch in type, dimension or value.
    UserWarning: if `nMic` not big enough for the required sht order.
    TODO: ValueError: if the array order is not big enough.

    Notes
    -----
    Generate the filters to convert microphone signals from a spherical
    microphone array to SH signals, based on an ideal theoretical model of 
    the array. The filters are generated as a least-squares
    solution with a constraint on filter amplification, using Tikhonov
    regularization. The method formulates the LS problem in the spherical
    harmonic domain, by expressing the array response to an order-limited
    series of SH coefficients, similar to

        Jin, C.T., Epain, N. and Parthy, A., 2014.
        Design, optimization and evaluation of a dual-radius spherical microphone array.
        IEEE/ACM Transactions on Audio, Speech, and Language Processing, 22(1), pp.193-204.

    """

    _validate_float('R', R, positive=True)
    _validate_ndarray_2D('mic_dirsAziElev', mic_dirsAziElev, shape1=C-1)
    _validate_int('order_sht', order_sht, positive=True)
    _validate_int('Lfilt', Lfilt, positive=True, parity='even')
    _validate_int('fs', fs, positive=True)
    _validate_float('amp_threshold', amp_threshold)

    f = np.arange(Lfilt // 2 + 1) * fs / Lfilt
    num_f = f.size
    kR = 2 * np.pi * f * R / c
    kR_max = kR[-1]

    nMic = mic_dirsAziElev.shape[0]
    # Adequate sht order to the number of microphones
    if order_sht > np.sqrt(nMic) - 1:
        order_sht = int(np.floor(np.sqrt(nMic) - 1))
        warnings.warn("Set order too high for the number of microphones, should be N<=np.sqrt(Q)-1. Auto set to "+str(order_sht), UserWarning)

    mic_dirsAziIncl = elev2incl(mic_dirsAziElev)
    order_array = int(np.floor(2 * kR_max))

    # TODO: check validity of the approach
    if order_array <= 1:
        raise ValueError("Order array <= 1. Consider increasing R or fs.")

    Y_array = np.sqrt(4 * np.pi) * get_sh(order_array, mic_dirsAziIncl, 'real')

    # Modal responses
    bN = sph_modal_coefs(order_array, kR, 'rigid') / (4 * np.pi)  # due to modified SHs, the 4pi term disappears from the plane wave expansion

    # Array response in the SHD
    H_array = np.zeros((nMic, np.power(order_array+1, 2), num_f), dtype='complex')
    for kk in range(num_f):
        temp_b = bN[kk, :].T
        B = np.diag(replicate_per_order(temp_b))
        H_array[:, :, kk] = np.matmul(Y_array, B)

    a_dB = amp_threshold
    alpha = complex(np.power(10, a_dB / 20))  # Explicit casting to allow negative sqrt (a_dB < 0)
    beta = 1 / (2 * alpha)
    H_filt = np.zeros((np.power(order_sht+1,2), nMic, num_f), dtype='complex')
    for kk in range(num_f):
        tempH_N = H_array[:, :, kk]
        tempH_N_trunc = tempH_N[:, :np.power(order_sht+1,2)]
        H_filt[:, :, kk] = np.matmul(tempH_N_trunc.T.conj(), np.linalg.inv(np.matmul(tempH_N, tempH_N.T.conj()) + np.power(beta, 2) * np.eye(nMic)))

    # Time domain filters
    h_filt = H_filt.copy()
    h_filt[:, :, -1] = np.abs(h_filt[:, :, -1])
    h_filt = np.concatenate((h_filt, np.conj(h_filt[:, :, -2:0:-1])), axis=2)
    h_filt = np.real(np.fft.ifft(h_filt, axis=2))
    h_filt = np.fft.fftshift(h_filt, axes=2)

    # TODO: check return ordering
    return h_filt, H_filt
