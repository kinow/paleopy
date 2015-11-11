
import os
import sys
import numpy as np
import pandas as pd
import h5py
import json
import seaborn as sns

from ..markov import *
from ..utils import seasons_params

class WR:

    """
    base class for weather regimes calculations and plots
    takes either a proxy or ensemble instance and either 'SW Pacific Regimes' or 'Kidson Types'
    """
    def __init__(self, obj, json_file='./jsons/WRs.json', classification='Kidson Types'):
        super(WR, self).__init__()
              
        # the parent can be either an instance of a `proxy` or `ensemble` class
        self.parent = obj
        
        self.json_file = json_file 
        self.classification = classification
        
        # get the season, and the analog years
        self.season = self.parent.season
        self.analog_years = self.parent.analog_years
        self.detrend = self.parent.detrend
        self.climatology = self.parent.climatology
        if self.parent.description == 'proxy': 
            self.sitename = self.parent.sitename
        
    def _get_WR_json(self): 
        with open(self.json_file, 'r') as f:
            dict_json = json.loads(f.read())
        return dict_json
            
    def _get_WR_ts(self): 
        if not(hasattr(self, 'dict_json')): 
            self.dict_json = self._get_WR_json()
        csv = self.dict_json[self.classification]['WR_TS']
        wr_ts = pd.read_csv(csv, parse_dates=True, index_col=0)
        return wr_ts
    
    def _get_WR_MC(self): 
        if not(hasattr(self, 'dict_json')): 
            self.dict_json = self._get_WR_json()
        f = h5py.File(self.dict_json[self.classification]['Markov Chains'], mode='r')
        MC_probs = f[self.season]['probs'].value
        MC_probs_classes = f[self.season]['probs'].attrs['classes']
        f.close()
        MC_probs_classes = MC_probs_classes.split(',')
        MC_probs = pd.DataFrame(MC_probs, index=MC_probs_classes)
        MC_probs = MC_probs.reindex(self.dict_json[self.classification]['types'])
        # The MC_probs contains the frequencies 
        # of each type in the 1000 simulations
        self.MC_probs = MC_probs
        return self
        
    def _get_season_ts(self): 
        if not(hasattr(self,'wr_ts')): 
            wr_ts = self._get_WR_ts()
        ts = wr_ts.copy()
        ts.loc[:,'month'] = ts.index.month

        sparams = seasons_params.seasons_params()
        m = list(range(1,13)) + list(range(1,13))
        m = m[(sparams[self.season][1]-sparams[self.season][0]+12):(sparams[self.season][1]+12)]

        # selects the season
        ts_seas = ts[ts['month'].isin(m)]
        ts_seas = ts_seas.drop('month', axis=1)
        
        return ts_seas
    
    def _get_clim_probs(self): 
        if not(hasattr(self, 'ts_seas')): 
            ts_seas = self._get_season_ts()
        ts = ts_seas.ix[str(self.climatology[0]): str(self.climatology[1])].copy()
        types = self.dict_json[self.classification]['types']
        clim_probs = get_probs(ts['type'], types)
        clim_probs = pd.Series(clim_probs, index=types)
        return clim_probs
        
    def _get_compos_probs(self, analog_years): 
        """
        Arguments
        ---------
        
        analog_years : list
                       list of analog years
                       
        Return
        ------
        
        obs_probs : pandas.Series
                    observed probabilities
        """
        if not(hasattr(self, 'ts_seas')): 
            ts_seas = self._get_season_ts()
        ayears = list(map(str, analog_years))
        ts = ts_seas.copy()
        ts = pd.concat([ts.ix[l] for l in ayears])
        types = self.dict_json[self.classification]['types']
        obs_probs = get_probs(ts['type'], types)
        obs_probs = pd.Series(obs_probs, index=types)
        return obs_probs
    
    def probs_anomalies(self, kind='one'): 
        """
        Arguments
        ---------
        
        kind : string
               if kind == 'one': 
                   either for a `proxy` or for all the years
                   in an `ensemble` as a whole
               if kind == 'many':
                   for each proxy record in an `ensemble` object
                       
        Return
        ------
        
        anoms_probs : pandas.Series
                      probabilities anomalies
        
        """
        
        # get the climatological probabilities
        clim_probs = self._get_clim_probs()
        
        if kind == 'one': 
            obs_probs = self._get_compos_probs(self.analog_years)
            df = obs_probs - clim_probs
            if self.parent.description == 'proxy': 
                self.df_anoms = pd.DataFrame(df, columns=[self.sitename])
            else: 
                self.df_anoms = pd.DataFrame(df, columns=['ensemble'])
        if kind == 'many':
            """
            we can only calculate `many` anomalies 
            if the object passed to the WR instance 
            is an `ensemble` object
            """
            if self.parent.description != 'ensemble':
                print("""ERROR! cannot calculate `many` anomalies with a proxy
                object: need an `ensemble` object""")
                raise Exception("KIND ERROR")
            else: 
                df = {}
                d = self.parent.dict_proxies
                for k in d.keys():
                    obs_probs = self._get_compos_probs(analog_years = d[k]['analog_years'])
                    anoms = obs_probs - clim_probs
                    df[k] = anoms
                self.df_anoms = pd.DataFrame(df)
        