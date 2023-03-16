
import pytest
from frappy_HZB.probenwechsler import Magazin, Schoki


def test_magazin():
    nsamples = 12
    
    samplePos = 1
    test_sample = Schoki(samplePos=samplePos,type='Vollmilch')
    
    mag = Magazin(nsamples,'Storage')
    
    mag.insertSample(sample=test_sample)
    
    assert(mag.get_sample(samplePos) == test_sample)
    
    mag.removeSample(samplePos)
    
    assert(mag.get_sample(samplePos)== None)