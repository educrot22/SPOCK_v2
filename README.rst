.. image:: https://img.shields.io/badge/docs-dev-green.svg
    :target: https://educrot22.github.io/SPOCK_v2/index.html

.. image:: ./SPOCK_Figures/spock_v2_logo.png
   :width: 600

**SPOCK_v2** (Speculoos Observatory SChedule maKer) is a python package developed to handle the
planification of observation of the SPECULOOS telescopes. The project SPECULOOS -Search for habitable Planets EClipsing ULtra-cOOl Stars –
searches for potentially habitable exoplanets around the smallest and coolest stars
of the solar neighborhood `Link to site <https://www.speculoos.uliege.be/cms/c_4259452/fr/speculoos>`_. `v2`_ is the second version of the package, which is similar to the first version but suited to Python 3.12. The main goal of this new version is to be more modular and to allow the use of the package by all members of the SPECULOOS consortium.

*SPOCK_v2* allows you to schedule SPECULOOS core program targets on several criteria:

*  Visibility of the target

*  Priority (calculated from stellar parameters)

*  Number of hours already performed

*  Coordination between different site

as well as external program targets (planetary candidates, eclipsing binaries, complex rotators, etc)

Documentation SPOCK_v2
---------------------

You will find complete documentation (in dev) for setting up your project at `SPOCK Read
the Docs site <https://educrot22.github.io/SPOCK_v2/index.html>`_.


Installation
---------------------

.. _installation:


.. warning::
    You must be part of the SPECULOOS consortium to use *SPOCK*.


Install *SPOCK* locally::

    git clone git@github.com:educrot22/SPOCK_v2.git

    cd spock_v2

    pip install -r requirements.txt



More about *SPOCK*
---------------------

*SPOCK_v2* is presented in more details in `Sebastian et al. 2020 <http://arxiv.org/abs/2011.02069>`_.
