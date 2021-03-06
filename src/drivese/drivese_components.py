"""
driveSE_components.py
New components for hub, low speed shaft, main bearings, gearbox, bedplate and yaw bearings, as well as modified components from NacelleSE

Created by Ryan King 2013. Edited by Taylor Parsons 2014
Copyright (c) NREL. All rights reserved.
"""

from openmdao.main.api import Component, Assembly
from openmdao.main.datatypes.api import Float, Bool, Int, Str, Array, Enum

import numpy as np
from math import pi, cos, sqrt, radians, sin, exp, log10, log, floor, ceil
import algopy
import scipy as scp
import scipy.optimize as opt
from scipy import integrate

from drivese_utils import seed_bearing_table, fatigue_for_bearings, fatigue2_for_bearings, resize_for_bearings, get_rotor_mass, get_L_rb


#-------------------------------------------------------------------------------
# Components
#-------------------------------------------------------------------------------

class LowSpeedShaft_drive4pt(Component):
    ''' LowSpeedShaft class
          The LowSpeedShaft class is used to represent the low speed shaft component of a wind turbine drivetrain. 
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    # variables
    rotor_bending_moment_x = Float(iotype='in', units='N*m', desc='The bending moment about the x axis')
    rotor_bending_moment_y = Float(iotype='in', units='N*m', desc='The bending moment about the y axis')
    rotor_bending_moment_z = Float(iotype='in', units='N*m', desc='The bending moment about the z axis')
    rotor_force_x = Float(iotype='in', units='N', desc='The force along the x axis applied at hub center')
    rotor_force_y = Float(iotype='in', units='N', desc='The force along the y axis applied at hub center')
    rotor_force_z = Float(iotype='in', units='N', desc='The force along the z axis applied at hub center')
    rotor_mass = Float(iotype='in', units='kg', desc='rotor mass')
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    machine_rating = Float(iotype='in', units='kW', desc='machine_rating machine rating of the turbine')
    gearbox_mass = Float(iotype='in', units='kg', desc='Gearbox mass')
    carrier_mass = Float(iotype='in', units='kg', desc='Carrier mass')
    overhang = Float(iotype='in', units='m', desc='Overhang distance')
    gearbox_cm = Array(iotype = 'in', units = 'm', desc = 'center of mass of gearbox')
    gearbox_length = Float(iotype='in', units='m', desc='gearbox length')
    flange_length = Float(iotype ='in', units='m', desc ='flange length')

    # parameters
    shrink_disc_mass = Float(iotype='in', units='kg', desc='Mass of the shrink disc')# shrink disk or flange addtional mass
    shaft_angle = Float(iotype='in', units='deg', desc='Angle of the LSS inclindation with respect to the horizontal')
    shaft_ratio = Float(iotype='in', desc='Ratio of inner diameter to outer diameter.  Leave zero for solid LSS')
    mb1Type = Str(iotype='in',desc='Main bearing type: CARB, TRB1 or SRB')
    mb2Type = Str(iotype='in',desc='Second bearing type: CARB, TRB1 or SRB')

    L_rb = Float(iotype='in', units='m', desc='distance between hub center and upwind main bearing')
    check_fatigue = Int(iotype = 'in', desc = 'turns on and off fatigue check')
    fatigue_exponent = Float(0,iotype = 'in', desc = 'fatigue exponent of material')
    S_ut = Float(iotype = 'in', units = 'Pa', desc = 'ultimate tensile strength of material')
    weibull_A = Float(iotype = 'in', units = 'm/s', desc = 'weibull scale parameter "A" of 10-minute windspeed probability distribution')
    weibull_k = Float(iotype = 'in', desc = 'weibull shape parameter "k" of 10-minute windspeed probability distribution')
    blade_number = Float(iotype = 'in', desc = 'number of blades on rotor, 2 or 3')
    cut_in = Float(iotype = 'in', units = 'm/s', desc = 'cut-in windspeed')
    cut_out = Float(iotype = 'in', units = 'm/s', desc = 'cut-out windspeed')
    Vrated = Float(iotype = 'in', units = 'm/s', desc = 'rated windspeed')
    T_life = Float(iotype = 'in', units = 'yr', desc = 'cut-in windspeed')
    IEC_Class = Str(iotype='in',desc='IEC class letter: A, B, or C')
    DrivetrainEfficiency = Float(iotype = 'in', desc = 'overall drivettrain efficiency')
    rotor_freq = Float(iotype = 'in', units = 'rpm', desc='rated rotor speed')
    availability = Float(.95,iotype = 'in', desc = 'turbine availability')

    rotor_thrust_distribution = Array(iotype='in', units ='N', desc = 'thrust distribution across turbine life')
    rotor_thrust_count = Array(iotype='in', desc = 'corresponding cycle array for thrust distribution')
    rotor_Fy_distribution = Array(iotype='in', units ='N', desc = 'Fy distribution across turbine life')
    rotor_Fy_count = Array(iotype='in', desc = 'corresponding cycle array for Fy distribution')
    rotor_Fz_distribution = Array(iotype='in', units ='N', desc = 'Fz distribution across turbine life')
    rotor_Fz_count = Array(iotype='in', desc = 'corresponding cycle array for Fz distribution') 
    rotor_torque_distribution = Array(iotype='in', units ='N*m', desc = 'torque distribution across turbine life')
    rotor_torque_count = Array(iotype='in', desc = 'corresponding cycle array for torque distribution') 
    rotor_My_distribution = Array(iotype='in', units ='N*m', desc = 'My distribution across turbine life')
    rotor_My_count = Array(iotype='in', desc = 'corresponding cycle array for My distribution') 
    rotor_Mz_distribution = Array(iotype='in', units ='N*m', desc = 'Mz distribution across turbine life')
    rotor_Mz_count = Array(iotype='in', desc = 'corresponding cycle array for Mz distribution') 
    
    # outputs
    design_torque = Float(iotype='out', units='N*m', desc='lss design torque')
    design_bending_load = Float(iotype='out', units='N', desc='lss design bending load')
    length = Float(iotype='out', units='m', desc='lss length')
    diameter1 = Float(iotype='out', units='m', desc='lss outer diameter at main bearing')
    diameter2 = Float(iotype='out', units='m', desc='lss outer diameter at second bearing')
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
    FW_mb1 = Float(iotype='out', units='m', desc='facewidth of upwind main bearing') 
    FW_mb2 = Float(iotype='out', units='m', desc='facewidth of main bearing')     
    bearing_mass1 = Float(iotype='out', units = 'kg', desc='main bearing mass')
    bearing_mass2 = Float(iotype='out', units = 'kg', desc='second bearing mass')
    bearing_location1 = Array(np.array([0,0,0]),iotype='out', units = 'm', desc = 'main bearing 1 center of mass')
    bearing_location2 = Array(np.array([0,0,0]),iotype='out', units = 'm', desc = 'main bearing 2 center of mass')

    def __init__(self):
        '''
        '''

        super(LowSpeedShaft_drive4pt, self).__init__()
    
    def execute(self):
        #Hub Forces
        F_r_x = self.rotor_force_x            #External F_x
        F_r_y = self.rotor_force_y                 #External F_y
        F_r_z = self.rotor_force_z                  #External F_z
        M_r_x = self.rotor_bending_moment_x
        M_r_y = self.rotor_bending_moment_y
        M_r_z = self.rotor_bending_moment_z

        #input parameters
        g=9.81
        gamma=self.shaft_angle #deg LSS angle wrt horizontal
        PSF=1
        check_fatigue = self.check_fatigue
        blade_number = self.blade_number
        V_0 = self.cut_in
        V_f = self.cut_out
        V_rated = self.Vrated
        T_life =self.T_life
        IEC_Class_Letter = self.IEC_Class
        rotor_mass = self.rotor_mass
        rotor_diameter = self.rotor_diameter
        machine_rating = self.machine_rating
        DrivetrainEfficiency = self.DrivetrainEfficiency
        rotor_freq = self.rotor_freq

        if rotor_mass ==0:
          rotor_mass = get_rotor_mass(self.machine_rating)

        if self.flange_length == 0:
            flange_length = 0.9918*exp(.0068*self.rotor_diameter)
        else:
            flange_length = self.flange_length
                
        # initialization for iterations    
        L_ms_new = 0.0
        L_ms_0=0.5 # main shaft length downwind of main bearing
        L_ms=L_ms_0
        tol=1e-4 
        check_limit = 1.0
        dL=0.05
        counter = 0
        N_count=50
        N_count_2=2
        len_pts=101
        D_max=1
        D_min=0.2
        sR = self.shaft_ratio

        #Distances
        if self.L_rb == 0: #distance from hub center to main bearing
          L_rb = 0.007835*rotor_diameter+0.9642
        else:
          L_rb = self.L_rb

        L_bg = 6.11-L_rb    #distance from first main bearing to gearbox yokes  # to add as an input
        L_as = L_ms/2.0     #distance from main bearing to shaft center
        L_gb = 0.0          #distance to gbx center from trunnions in x-dir # to add as an input
        H_gb = 1.0          #distance to gbx center from trunnions in z-dir # to add as an input     
        L_gp = 0.825        #distance from gbx coupling to gbx trunnions
        L_cu = L_ms + 0.5   #distance from upwind main bearing to upwind carrier bearing 0.5 meter is an estimation # to add as an input
        L_cd = L_cu + 0.5   #distance from upwind main bearing to downwind carrier bearing 0.5 meter is an estimation # to add as an input
        
        #material properties
        E=2.1e11
        density=7800.0
        n_safety = 2.5 # According to AGMA, takes into account the peak load safety factor
        Sy = 66000 #psi

        #unit conversion
        u_knm_inlb = 8850.745454036
        u_in_m = 0.0254000508001

        #bearing deflection limits
        MB_limit = 0.026
        CB_limit = 4.0/60.0/180.0*pi
        TRB1_limit = 3.0/60.0/180.0*pi
        n_safety_brg = 1.0

        length_max = self.overhang - L_rb + (self.gearbox_cm[0] -self.gearbox_length/2.) #modified length limit 7/29

        while abs(check_limit) > tol and L_ms_new < length_max:
            counter = counter+1
            if L_ms_new > 0:
                L_ms=L_ms_new
            else:
                L_ms=L_ms_0

            #Distances
            L_as = L_ms/2.0     #distance from main bearing to shaft center
            L_cu = L_ms + 0.5   #distance from upwind main bearing to upwind carrier bearing 0.5 meter is an estimation # to add as an input
            L_cd = L_cu + 0.5   #distance from upwind main bearing to downwind carrier bearing 0.5 meter is an estimation # to add as an input

            #Weight properties
            rotorWeight=self.rotor_mass*g                             #rotor weight
            lssWeight = pi/3.0*(D_max**2 + D_min**2 + D_max*D_min)*L_ms*density*g/4.0 ##
            lss_mass = lssWeight/g
            gbxWeight = self.gearbox_mass*g                               #gearbox weight
            carrierWeight = self.carrier_mass*g                       #carrier weight
            shrinkDiscWeight = self.shrink_disc_mass*g

            #define LSS
            x_ms = np.linspace(L_rb, L_ms+L_rb, len_pts)
            x_rb = np.linspace(0.0, L_rb, len_pts)
            y_gp = np.linspace(0, L_gp, len_pts)

            F_mb_x = -F_r_x - rotorWeight*sin(radians(gamma))
            F_mb_y = +M_r_z/L_bg - F_r_y*(L_bg + L_rb)/L_bg
            F_mb_z = (-M_r_y + rotorWeight*(cos(radians(gamma))*(L_rb + L_bg)\
                       + sin(radians(gamma))*H_gb) + lssWeight*(L_bg - L_as)\
                       * cos(radians(gamma)) + shrinkDiscWeight*cos(radians(gamma))\
                       *(L_bg - L_ms) - gbxWeight*cos(radians(gamma))*L_gb - F_r_z*cos(radians(gamma))*(L_bg + L_rb))/L_bg

            F_gb_x = -(lssWeight+shrinkDiscWeight+gbxWeight)*sin(radians(gamma))
            F_gb_y = -F_mb_y - F_r_y
            F_gb_z = -F_mb_z + (shrinkDiscWeight+rotorWeight+gbxWeight + lssWeight)*cos(radians(gamma)) - F_r_z

            My_ms = np.zeros(2*len_pts)
            Mz_ms = np.zeros(2*len_pts)

            for k in range(len_pts):
                My_ms[k] = -M_r_y + rotorWeight*cos(radians(gamma))*x_rb[k] + 0.5*lssWeight/L_ms*x_rb[k]**2 - F_r_z*x_rb[k]
                Mz_ms[k] = -M_r_z - F_r_y*x_rb[k]

            for j in range(len_pts):
                My_ms[j+len_pts] = -F_r_z*x_ms[j] - M_r_y + rotorWeight*cos(radians(gamma))*x_ms[j] - F_mb_z*(x_ms[j]-L_rb) + 0.5*lssWeight/L_ms*x_ms[j]**2
                Mz_ms[j+len_pts] = -M_r_z - F_mb_y*(x_ms[j]-L_rb) -F_r_y*x_ms[j]

            x_shaft = np.concatenate([x_rb, x_ms])

            MM_max=np.amax((My_ms**2+Mz_ms**2)**0.5)
            Index=np.argmax((My_ms**2+Mz_ms**2)**0.5)

            MM_min = ((My_ms[-1]**2+Mz_ms[-1]**2)**0.5)
            #Design shaft OD 
            MM=MM_max
            D_max=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb/1000)**2+3.0*(M_r_x*u_knm_inlb/1000)**2)**0.5)**(1.0/3.0)*u_in_m

            #OD at end
            MM=MM_min
            D_min=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb/1000)**2+3.0*(M_r_x*u_knm_inlb/1000)**2)**0.5)**(1.0/3.0)*u_in_m

            #Estimate ID
            D_in=sR*D_max
            D_max = (D_max**4 + D_in**4)**0.25
            D_min = (D_min**4 + D_in**4)**0.25
           
            lssWeight_new=((pi/3)*(D_max**2+D_min**2+D_max*D_min)*(L_ms)*density/4+(-pi/4*(D_in**2)*density*(L_ms)))*g

            def deflection(F_r_z,W_r,gamma,M_r_y,f_mb_z,L_rb,W_ms,L_ms,z):
                return -F_r_z*z**3/6.0 + W_r*cos(radians(gamma))*z**3/6.0 - M_r_y*z**2/2.0 - f_mb_z*(z-L_rb)**3/6.0 + W_ms/(L_ms + L_rb)/24.0*z**4
            
                     
            D1 = deflection(F_r_z,rotorWeight,gamma,M_r_y,F_mb_z,L_rb,lssWeight_new,L_ms,L_rb+L_ms)
            D2 = deflection(F_r_z,rotorWeight,gamma,M_r_y,F_mb_z,L_rb,lssWeight_new,L_ms,L_rb)
            C1 = -(D1-D2)/L_ms;
            C2 = D2-C1*(L_rb);
            
            I_2=pi/64.0*(D_max**4 - D_in**4)

            def gx(F_r_z,W_r,gamma,M_r_y,f_mb_z,L_rb,W_ms,L_ms,C1,z):
                return -F_r_z*z**2/2.0 + W_r*cos(radians(gamma))*z**2/2.0 - M_r_y*z - f_mb_z*(z-L_rb)**2/2.0 + W_ms/(L_ms + L_rb)/6.0*z**3 + C1

            theta_y = np.zeros(len_pts)
            d_y = np.zeros(len_pts)

            for kk in range(len_pts):
                theta_y[kk]=gx(F_r_z,rotorWeight,gamma,M_r_y,F_mb_z,L_rb,lssWeight_new,L_ms,C1,x_ms[kk])/E/I_2
                d_y[kk]=(deflection(F_r_z,rotorWeight,gamma,M_r_y,F_mb_z,L_rb,lssWeight_new,L_ms,x_ms[kk])+C1*x_ms[kk]+C2)/E/I_2

            check_limit = abs(abs(theta_y[-1])-TRB1_limit/n_safety_brg)

            if check_limit < 0:
                L_ms_new = L_ms + dL

            else:
                L_ms_new = L_ms + dL

         #Initialization
        L_mb=L_ms_new
        counter_ms=0
        check_limit_ms=1.0
        L_mb_new=0.0
        L_mb_0=L_mb                     #main shaft length
        L_ms = L_ms_new
        dL_ms = 0.05
        dL = 0.0025

        while abs(check_limit_ms)>tol and L_mb_new < length_max:
            counter_ms= counter_ms + 1
            if L_mb_new > 0:
                L_mb=L_mb_new
            else:
                L_mb=L_mb_0

            counter = 0.0
            check_limit=1.0
            L_ms_gb_new=0.0
            L_ms_0=0.5 #mainshaft length
            L_ms = L_ms_0


            while abs(check_limit) > tol and counter <N_count_2:
                counter =counter+1
                if L_ms_gb_new>0.0:
                    L_ms_gb = L_ms_gb_new
                else:
                    L_ms_gb = L_ms_0

                #Distances
                L_as = (L_ms_gb+L_mb)/2.0
                L_cu = (L_ms_gb + L_mb) + 0.5
                L_cd = L_cu + 0.5

                #Weight
                lssWeight_new=((pi/3)*(D_max**2+D_min**2+D_max*D_min)*(L_ms_gb + L_mb)*density/4+(-pi/4*(D_in**2)*density*(L_ms_gb + L_mb)))*g

                #define LSS
                x_ms = np.linspace(L_rb + L_mb, L_ms_gb + L_mb +L_rb, len_pts)
                x_mb = np.linspace(L_rb, L_mb+L_rb, len_pts)
                x_rb = np.linspace(0.0, L_rb, len_pts)
                y_gp = np.linspace(0, L_gp, len_pts)

                F_mb2_x = -F_r_x - rotorWeight*sin(radians(gamma))
                F_mb2_y = -M_r_z/L_mb + F_r_y*(L_rb)/L_mb
                F_mb2_z = (M_r_y - rotorWeight*cos(radians(gamma))*L_rb \
                          -lssWeight*L_as*cos(radians(gamma)) - shrinkDiscWeight*(L_mb+L_ms_0)*cos(radians(gamma)) \
                           + gbxWeight*cos(radians(gamma))*L_gb + F_r_z*cos(radians(gamma))*L_rb)/L_mb

                F_mb1_x = 0.0
                F_mb1_y = -F_r_y - F_mb2_y
                F_mb1_z = (rotorWeight + lssWeight + shrinkDiscWeight)*cos(radians(gamma)) - F_r_z - F_mb2_z

                F_gb_x = -(lssWeight+shrinkDiscWeight+gbxWeight)*sin(radians(gamma))
                F_gb_y = -F_mb_y - F_r_y
                F_gb_z = -F_mb_z + (shrinkDiscWeight+rotorWeight+gbxWeight + lssWeight)*cos(radians(gamma)) - F_r_z

                My_ms = np.zeros(3*len_pts)
                Mz_ms = np.zeros(3*len_pts)

                for k in range(len_pts):
                    My_ms[k] = -M_r_y + rotorWeight*cos(radians(gamma))*x_rb[k] + 0.5*lssWeight/(L_mb+L_ms_0)*x_rb[k]**2 - F_r_z*x_rb[k]
                    Mz_ms[k] = -M_r_z - F_r_y*x_rb[k]

                for j in range(len_pts):
                    My_ms[j+len_pts] = -F_r_z*x_mb[j] - M_r_y + rotorWeight*cos(radians(gamma))*x_mb[j] - F_mb1_z*(x_mb[j]-L_rb) + 0.5*lssWeight/(L_mb+L_ms_0)*x_mb[j]**2
                    Mz_ms[j+len_pts] = -M_r_z - F_mb1_y*(x_mb[j]-L_rb) -F_r_y*x_mb[j]

                for l in range(len_pts):
                    My_ms[l + 2*len_pts] = -F_r_z*x_ms[l] - M_r_y + rotorWeight*cos(radians(gamma))*x_ms[l] - F_mb1_z*(x_ms[l]-L_rb) -F_mb2_z*(x_ms[l] - L_rb - L_mb) + 0.5*lssWeight/(L_mb+L_ms_0)*x_ms[l]**2
                    Mz_ms[l + 2*len_pts] = -M_r_z - F_mb_y*(x_ms[l]-L_rb) -F_r_y*x_ms[l]

                x_shaft = np.concatenate([x_rb, x_mb, x_ms])

                MM_max=np.amax((My_ms**2+Mz_ms**2)**0.5)
                Index=np.argmax((My_ms**2+Mz_ms**2)**0.5)

                MM_min = ((My_ms[-1]**2+Mz_ms[-1]**2)**0.5)

                MM_med = ((My_ms[-1 - len_pts]**2 + Mz_ms[-1 - len_pts]**2)**0.5)

                #Design Shaft OD using static loading and distortion energy theory
                MM=MM_max
                D_max=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb/1000)**2+3.0*(M_r_x*u_knm_inlb/1000)**2)**0.5)**(1.0/3.0)*u_in_m

                #OD at end
                MM=MM_min
                D_min=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb/1000)**2+3.0*(M_r_x*u_knm_inlb/1000)**2)**0.5)**(1.0/3.0)*u_in_m

                MM=MM_med
                D_med=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb/1000)**2+3.0*(M_r_x*u_knm_inlb/1000)**2)**0.5)**(1.0/3.0)*u_in_m

                #Estimate ID
                D_in=sR*D_max
                D_max = (D_max**4 + D_in**4)**0.25
                D_min = (D_min**4 + D_in**4)**0.25
                D_med = (D_med**4 + D_in**4)**0.25

                lssWeight_new = (density*pi/12.0*L_mb*(D_max**2+D_med**2 + D_max*D_med) - density*pi/4.0*D_in**2*L_mb)*g

                #deflection between mb1 and mb2
                def deflection1(F_r_z,W_r,gamma,M_r_y,f_mb1_z,L_rb,W_ms,L_ms,L_mb,z):
                    return -F_r_z*z**3/6.0 + W_r*cos(radians(gamma))*z**3/6.0 - M_r_y*z**2/2.0 - f_mb1_z*(z-L_rb)**3/6.0 + W_ms/(L_ms + L_mb)/24.0*z**4
                
                D11 = deflection1(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,L_rb,lssWeight_new,L_ms,L_mb,L_rb+L_mb)
                D21 = deflection1(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,L_rb,lssWeight_new,L_ms,L_mb,L_rb)
                C11 = -(D11-D21)/L_mb
                C21 = -D21-C11*(L_rb)

                I_2=pi/64.0*(D_max**4 - D_in**4)

                def gx1(F_r_z,W_r,gamma,M_r_y,f_mb1_z,L_rb,W_ms,L_ms,L_mb,C11,z):
                    return -F_r_z*z**2/2.0 + W_r*cos(radians(gamma))*z**2/2.0 - M_r_y*z - f_mb1_z*(z - L_rb)**2/2.0 + W_ms/(L_ms + L_mb)/6.0*z**3 + C11

                theta_y = np.zeros(2*len_pts)
                d_y = np.zeros(2*len_pts)

                for kk in range(len_pts):
                    theta_y[kk]=gx1(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,L_rb,lssWeight_new,L_ms,L_mb,C11,x_mb[kk])/E/I_2
                    d_y[kk]=(deflection1(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,L_rb,lssWeight_new,L_ms,L_mb,x_mb[kk])+C11*x_mb[kk]+C21)/E/I_2

                #Deflection between mb2 and gbx
                def deflection2(F_r_z,W_r,gamma,M_r_y,f_mb1_z,f_mb2_z,L_rb,W_ms,L_ms,L_mb,z):
                    return -F_r_z*z**3/6.0 + W_r*cos(radians(gamma))*z**3/6.0 - M_r_y*z**2/2.0 - f_mb1_z*(z-L_rb)**3/6.0 + -f_mb2_z*(z - L_rb - L_mb)**3/6.0 + W_ms/(L_ms + L_mb)/24.0*z**4
            
                def gx2(F_r_z,W_r,gamma,M_r_y,f_mb1_z,f_mb2_z,L_rb,W_ms,L_ms,L_mb,z):
                    return -F_r_z*z**2/2.0 + W_r*cos(radians(gamma))*z**2/2.0 - M_r_y*z - f_mb1_z*(z - L_rb)**2/2.0 - f_mb2_z*(z - L_rb - L_mb)**2/2.0 + W_ms/(L_ms + L_mb)/6.0*z**3

                D12 = deflection2(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,F_mb2_z,L_rb,lssWeight_new,L_ms,L_mb,L_rb+L_mb)
                D22 = gx2(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,F_mb2_z,L_rb,lssWeight_new,L_ms,L_mb,L_rb+L_mb)
                C12 = gx1(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,L_rb,lssWeight_new,L_ms,L_mb,C11,x_mb[-1])-D22
                C22 = -D12-C12*(L_rb + L_mb);

                for kk in range(len_pts):
                    theta_y[kk + len_pts]=(gx2(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,F_mb2_z,L_rb,lssWeight_new,L_ms,L_mb,x_ms[kk]) + C12)/E/I_2
                    d_y[kk + len_pts]=(deflection2(F_r_z,rotorWeight,gamma,M_r_y,F_mb1_z,F_mb2_z,L_rb,lssWeight_new,L_ms,L_mb,x_ms[kk])+C12*x_ms[kk]+C22)/E/I_2

                check_limit = abs(abs(theta_y[-1])-TRB1_limit/n_safety_brg)

                if check_limit < 0:
                    L_ms__gb_new = L_ms_gb + dL
                else:
                    L_ms__gb_new = L_ms_gb + dL

                check_limit_ms = abs(abs(theta_y[-1]) - TRB1_limit/n_safety_brg)

                if check_limit_ms < 0:
                    L_mb_new = L_mb + dL_ms
                else:
                    L_mb_new = L_mb + dL_ms

        # fatigue check Taylor Parsons 6/14
        if check_fatigue == 1 or check_fatigue == 2:
          #start_time = time.time()

          #checks to make sure all inputs are reasonable
          if rotor_mass < 100:
              rotor_mass = get_rotor_mass(self.machine_rating)

          #Weibull Parameters
          weibullA=self.weibull_A
          weibullk=self.weibull_k

          g=9.81 
          #material properties 34CrNiMo6 steel +QT, large diameter
          E=2.1e11
          density=7800.0
          n_safety = 2.5
          Sy = 490.0e6 # Pa
          if self.S_ut > 0:
            Sut = self.S_ut
          else:
            Sut=700.0e6 #Pa

          #calculate material props for fatigue
          Sm=0.9*Sut #for bending situations, material strength at 10^3 cycles
          C_size=0.6 #diameter larger than 10"
          C_surf=4.51*(Sut/1e6)**-.265 #machined surface 272*(Sut/1e6)**-.995 #forged
          C_temp=1 #normal operating temps
          C_reliab=0.814 #99% reliability
          C_envir=1. #enclosed environment
          Se=C_size*C_surf*C_temp*C_reliab*C_envir*.5*Sut #modified endurance limit for infinite life (should be Sf)\

          if self.fatigue_exponent!=0:
            SN_b = -1/self.fatigue_exponent
          else:
            Nfinal = 5e8 #point where fatigue limit occurs under hypothetical S-N curve TODO adjust to fit actual data
            z=log10(1e3)-log10(Nfinal)  #assuming no endurance limit (high strength steel)
            SN_b=1/z*log10(Sm/Se)
          SN_a=Sm/(1000.**SN_b)
          # print 'm:', -1/SN_b
          # print 'a:', SN_a
          if check_fatigue == 1:
              #Rotor Loads calculations using DS472
              R=rotor_diameter/2.0
              rotor_torque = (machine_rating * 1000 / DrivetrainEfficiency) / (rotor_freq * (pi/30))
              Tip_speed_ratio= rotor_freq/30.*pi*R/V_rated
              rho_air= 1.225 #kg/m^3 density of air
              p_o = 4./3*rho_air*((4*pi*rotor_freq/60*R/3)**2+V_rated**2)*(pi*R/(blade_number*Tip_speed_ratio*(Tip_speed_ratio**2+1)**(.5)))
              # print 'po:',p_o
              n_c=blade_number*rotor_freq/60 #characteristic frequency on rotor from turbine of given blade number [Hz]
              N_f=self.availability*n_c*(T_life*365*24*60*60)*exp(-(V_0/weibullA)**weibullk)-exp(-(V_f/weibullA)**weibullk) #number of rotor rotations based off of weibull curve. .827 comes from lower rpm than rated at lower wind speeds

              k_b= 2.5 #calculating rotor pressure from all three blades. Use kb=1 for individual blades

              if IEC_Class_Letter == 'A': # From IEC 61400-1 TODO consider calculating based off of 10-minute windspeed and weibull parameters, include neighboring wake effects?
                I_t=0.18 
              elif IEC_Class_Letter == 'B':
                I_t=0.14
              else:
                I_t=0.12

              Beta=0.11*k_b*(I_t+0.1)*(weibullA+4.4)

              # find generic standardized stochastic load range distribution
              def standardrange(N, N_f, Beta, k_b): 
                  F_delta=(Beta*(log10(N_f)-log10(N)))+0.18
                  if F_delta>=2*k_b:
                    F_delta=0.
                  return F_delta
              # print N_f

              def rounddown(x,step):
                return int(floor(x/step))*step

              def roundup(x,step):
                  return int(ceil(x/step))*step

              #for analysis with N on log scale, makes larger loads contain finer step sizes
              num_pts=100
              N=np.logspace( (log10(N_f)-(2*k_b-0.18)/Beta) , log10(N_f) , endpoint=True , num=num_pts) # with zeros: N=np.logspace(log10(1.0),log10(N_f),endpoint=True,num=num_pts)
              N_rotor = N_f/3.
              F_stoch=N.copy()

              for i in range(num_pts):
                  N[i]=roundup(N[i],1)

              #print N

              k_r=0.8 #assuming natural frequency of rotor is significantly larger than rotor rotational frequency

              for i in range(num_pts):
                F_stoch[i] = standardrange(N[i],N_f,Beta,k_b)
              # print 'Standard1:'
              # print F_stoch

              Fx_factor = (.3649*log(rotor_diameter)-1.074)
              Mx_factor = (.0799*log(rotor_diameter)-.2577)
              My_factor = (.172*log(rotor_diameter)-.5943)
              Mz_factor = (.1659*log(rotor_diameter)-.5795)

              Fx_stoch = (F_stoch.copy()*0.5*p_o*(R))*Fx_factor
              Mx_stoch = (F_stoch.copy()*0.45*p_o*(R)**2)*Mx_factor#*0.31
              My_stoch = (F_stoch.copy()*0.33*p_o*k_r*(R)**2)*My_factor#*0.25
              Mz_stoch = (F_stoch.copy()*0.33*p_o*k_r*(R)**2)*Mz_factor#*0.25 

              # print np.max(N)
              # print np.min(N)
              # print np.max(Fx_stoch)
              # print np.min(Fx_stoch)
              # print np.max(Mx_stoch)
              # print np.min(Mx_stoch)
              # print np.max(My_stoch)
              # print np.min(My_stoch)
              # print np.max(Mz_stoch)
              # print np.min(Mz_stoch)    
              # print N
              # print Fx_stoch
              # print Mx_stoch          

              def Ninterp(S,a,b):
                  return (S/a)**(1/b)

              def Goodman(S_alt,S_mean,Sut):
                  return S_alt/(1-(S_mean/Sut))

              Fx_mean=0.5*p_o*R*blade_number*Fx_factor
              Mx_mean=0.5*rotor_torque*Mx_factor
              rotorWeight=rotor_mass*g

              # print 'Fx_max:', np.max(Fx_stoch) + Fx_mean
              # print 'Mx_max:', np.max(Mx_stoch) + Mx_mean
              # print 'My_max:', np.max(My_stoch)
              # print 'Mz_max:', np.max(Mz_stoch)
              # print 'occurance:', np.min(N)

              #upwind bearing calculations
              iterationstep=0.01
              diameter_limit = 5.0
              print ''
              while True:
                  D_in=sR*D_max
                  D_max = (D_max**4 + D_in**4)**0.25
                  D_min = (D_min**4 + D_in**4)**0.25
                  D_med = (D_med**4 + D_in**4)**0.25
                  I=(pi/64.0)*(D_max**4-D_in**4)
                  J=I*2
                  Area=pi/4.*(D_max**2-D_in**2)
                  LssWeight=density*9.81*(((pi/12)*(D_max**2+D_med**2+D_max*D_med)*(L_mb))-(pi/4*L_mb*D_in**2))

                  #create stochastic loads across N
                  stoch_bend1 = (My_stoch**2+Mz_stoch**2)**(0.5)*D_max/(2.*I)
                  stoch_shear1 = abs(Mx_stoch*D_max/(2.*J))
                  stoch_normal1 = Fx_stoch/Area*cos(radians(gamma))
                  stoch_stress1 = ((stoch_bend1+stoch_normal1)**2+3.*stoch_shear1**2)**(0.5)
                  
                  #create mean loads
                  mean_bend1 = 0 #Fz_mean*L_rb*D_max/(2.*I) #not mean, but deterministic
                  mean_shear1 = Mx_mean*D_max/(2.*J)
                  mean_normal1 = Fx_mean/Area*cos(radians(gamma))+(rotorWeight+LssWeight)*sin(radians(gamma))
                  mean_stress1 = ((mean_bend1+mean_normal1)**2+3.*mean_shear1**2)**(0.5)

                  #apply Goodman with compressive (-) mean stress
                  S_mod_stoch1=Goodman(stoch_stress1,-mean_stress1,Sut)

                  #Use Palmgren-Miner linear damage rule to add damage from stochastic load ranges
                  DEL_y=Fx_stoch.copy() #initialize
                  for i in range(num_pts):
                      DEL_y[i] = N[i]/(Ninterp(S_mod_stoch1[i],SN_a,SN_b))

                  Damage = scp.integrate.simps(DEL_y,x= N, even='avg') #damage from stochastic loading

                  #create deterministic loads occurring N_rotor times
                  determ_stress1 = abs(rotorWeight*cos(radians(gamma))*L_rb*D_max/(2.*I)) #only deterministic stress at mb1 is bending due to rotor weight

                  S_mod_determ=Goodman(determ_stress1,-mean_stress1,Sut)
                  # print 'before deterministic Damage:', Damage

                  Damage += N_rotor/(Ninterp(S_mod_determ,SN_a,SN_b))
                  # print 'Upwind Bearing Diameter:', D_max
                  # print 'Damage:', Damage
                  if Damage < 1 or D_max >= diameter_limit:
                      # print 'Upwind Bearing Diameter:', D_max
                      # print 'Damage:', Damage
                      # print 'unadjusted upwind diameter is %f m.' %(D_max)
                      #print (time.time() - start_time), 'seconds of total simulation time'
                      break
                  else:
                      D_max+=iterationstep

              #downwind bearing calculations
              diameter_limit = 5.0
              iterationstep=0.01

              while True:
                  I=(pi/64.0)*(D_med**4-D_in**4)
                  J=I*2
                  Area=pi/4.*(D_med**2-D_in**2)
                  LssWeight=density*9.81*(((pi/12)*(D_max**2+D_med**2+D_max*D_med)*(L_mb))-(pi/4*L_mb*D_in**2))
                  
                  Fz1stoch = (-My_stoch)/(L_mb)
                  Fy1stoch = Mz_stoch/L_mb
                  My2stoch = 0. #My_stoch - abs(Fz1stoch)*L_mb #=0
                  Mz2stoch = 0. #Mz_stoch - abs(Fy1stoch)*L_mb #=0

                  #create stochastic loads across N
                  stoch_bend2 = (My2stoch**2+Mz2stoch**2)**(0.5)*D_med/(2.*I)
                  stoch_shear2 = abs(Mx_stoch*D_med/(2.*J))
                  stoch_normal2 = Fx_stoch/Area*cos(radians(gamma)) #all normal force held by downwind bearing
                  stoch_stress2 = ((stoch_bend2+stoch_normal2)**2+3.*stoch_shear2**2)**(0.5)
                  #print stoch_stress2
                  
                  #create mean loads
                  mean_bend2 = 0. #Fz_mean*L_rb*D_med/(2.*I) #not mean, but deterministic
                  mean_shear2 = Mx_mean*D_med/(2.*J)
                  mean_normal2 = Fx_mean/Area*cos(radians(gamma))+(rotorWeight+LssWeight)*sin(radians(gamma))
                  mean_stress2 = ((mean_bend2+mean_normal2)**2+3.*mean_shear2**2)**(0.5)
                  #apply Goodman with compressive (-) mean stress
                  S_mod_stoch2=Goodman(stoch_stress2,-mean_stress2,Sut)

                  #Use Palmgren-Miner linear damage rule to add damage from stochastic load ranges
                  for i in range(num_pts):
                      DEL_y[i] = N[i]/(Ninterp(S_mod_stoch2[i],SN_a,SN_b))

                  Damage = scp.integrate.simps(DEL_y, x=N , even='avg') #damage from stochastic loading

                  #create deterministic loads occurring N_rotor times
                  Fz1determ = (gbxWeight*L_gb - LssWeight*.5*L_mb - rotorWeight*(L_mb+L_rb)) / (L_mb)
                  My2determ = gbxWeight*L_gb #-rotorWeight*(L_rb+L_mb) + Fz1determ*L_mb - LssWeight*.5*L_mb + gbxWeight*L_gb
                  determ_stress2 = abs(My2determ*D_med/(2.*I))

                  S_mod_determ2=Goodman(determ_stress2,-mean_stress2,Sut)

                  if S_mod_determ2 > 0:
                    Damage += N_rotor/(Ninterp(S_mod_determ2,SN_a,SN_b))
                  # print 'max stochastic:', np.max(S_mod_stoch2)
                  # print ''
                  # print 'Downwind Bearing Diameter:', D_med
                  # print 'Damage:', Damage
                  if Damage < 1 or D_med >= diameter_limit:
                      # print ''
                      # print 'Downwind Bearing Diameter:', D_med
                      # print 'Damage:', Damage
                      #print (time.time() - start_time), 'seconds of total simulation time'
                      break
                  else:
                      D_med+=iterationstep

              #begin bearing calculations
              N_bearings = N/blade_number #counts per rotation (not defined by characteristic frequency 3n_rotor)

              Fr1_range = ((abs(Fz1stoch)+abs(Fz1determ))**2 +Fy1stoch**2)**.5 #radial stochastic + deterministic mean
              Fa1_range = np.zeros(len(Fy1stoch))

              #...calculate downwind forces
              lss_weight=density*9.81*(((pi/12)*(D_max**2+D_med**2+D_max*D_med)*(L_mb))-(pi/4*L_mb*D_in**2))
              Fy2stoch = -Mz_stoch/(L_mb) #= -Fy1 - Fy_stoch
              Fz2stoch = -(lss_weight*2./3.*L_mb-My_stoch)/(L_mb) + (lss_weight+shrinkDiscWeight+gbxWeight)*cos(radians(gamma)) - rotorWeight #-Fz1 +Weights*cos(gamma)-Fz_stoch+Fz_mean (Fz_mean is in negative direction)
              Fr2_range = (Fy2stoch**2+(Fz2stoch+abs(-rotorWeight*L_rb + 0.5*lss_weight+gbxWeight*L_gb/L_mb))**2)**0.5
              Fa2_range = Fx_stoch*cos(radians(gamma)) + (rotorWeight+LssWeight)*sin(radians(gamma)) #axial stochastic + mean

              life_bearing = N_f/blade_number

              [D_max_a,FW_max,bearing1mass] = fatigue_for_bearings(D_max, Fr1_range, Fa1_range, N_bearings, life_bearing, self.mb1Type)
              [D_med_a,FW_med,bearing2mass] = fatigue_for_bearings(D_med, Fr2_range, Fa2_range, N_bearings, life_bearing, self.mb2Type)  

          elif check_fatigue == 2:
            Fx = self.rotor_thrust_distribution
            n_Fx = self.rotor_thrust_count
            Fy = self.rotor_Fy_distribution
            n_Fy = self.rotor_Fy_count
            Fz = self.rotor_Fz_distribution
            n_Fz = self.rotor_Fz_count
            Mx = self.rotor_torque_distribution
            n_Mx = self.rotor_torque_count
            My = self.rotor_My_distribution
            n_My = self.rotor_My_count
            Mz = self.rotor_Mz_distribution
            n_Mz = self.rotor_Mz_count

            print n_Fx
            print Fx*.5
            print Mx*.5
            print -1/SN_b

            def Ninterp(L_ult,L_range,m):
                return (L_ult/(.5*L_range))**m #TODO double-check that the input will be the load RANGE instead of load amplitudes. May also include means

            #upwind bearing calcs
            diameter_limit = 5.0
            iterationstep=0.01
            #upwind bearing calcs
            while True:
                Damage = 0
                Fx_ult = SN_a*(pi/4.*(D_max**2-D_in**2))
                Fyz_ult = SN_a*(pi*(D_max**4-D_in**4))/(D_max*64.)/L_rb
                Mx_ult = SN_a*(pi*(D_max**4-D_in**4))/(32*(3)**.5*D_max)
                Myz_ult = SN_a*(pi*(D_max**4-D_in**4))/(D_max*64.)
                if Fx_ult !=0 and np.all(n_Fx) != 0:
                    Damage+=scp.integrate.simps(n_Fx/Ninterp(Fx_ult,Fx,-1/SN_b),x=n_Fx,even = 'avg')
                if Fyz_ult !=0:
                    if np.all(n_Fy) != 0:
                        Damage+=scp.integrate.simps(abs(n_Fy/Ninterp(Fyz_ult,Fy,-1/SN_b)),x=n_Fy,even = 'avg')
                    if np.all(n_Fz) != 0:
                        Damage+=scp.integrate.simps(abs(n_Fz/Ninterp(Fyz_ult,Fz,-1/SN_b)),x=n_Fz,even = 'avg')
                if Mx_ult !=0 and np.all(n_Mx) != 0:
                    Damage+=scp.integrate.simps(abs(n_Mx/Ninterp(Mx_ult,Mx,-1/SN_b)),x=n_Mx,even = 'avg')
                if Myz_ult!=0:
                    if np.all(n_My) != 0:
                        Damage+=scp.integrate.simps(abs(n_My/Ninterp(Myz_ult,My,-1/SN_b)),x=n_My,even = 'avg')
                    if np.all(n_Mz) != 0:
                        Damage+=scp.integrate.simps(abs(n_Mz/Ninterp(Myz_ult,Mz,-1/SN_b)),x=n_Mz,even = 'avg')

                print 'Upwind Bearing Diameter:', D_max
                print 'Damage:', Damage

                if Damage <= 1 or D_max >= diameter_limit:
                    # print 'Upwind Bearing Diameter:', D_max
                    # print 'Damage:', Damage
                    #print (time.time() - start_time), 'seconds of total simulation time'
                    break
                else:
                    D_max+=iterationstep
            #downwind bearing calcs
            while True:
                Damage = 0
                Fx_ult = SN_a*(pi/4.*(D_med**2-D_in**2))
                Mx_ult = SN_a*(pi*(D_med**4-D_in**4))/(32*(3)**.5*D_med)
                if Fx_ult !=0:
                    Damage+=scp.integrate.simps(n_Fx/Ninterp(Fx_ult,Fx,-1/SN_b),x=n_Fx,even = 'avg')
                if Mx_ult !=0:
                    Damage+=scp.integrate.simps(n_Mx/Ninterp(Mx_ult,Mx,-1/SN_b),x=n_Mx,even = 'avg')
                print 'Downwind Bearing Diameter:', D_med
                print 'Damage:', Damage

                if Damage <= 1 or D_med>= diameter_limit:
                    # print 'Upwind Bearing Diameter:', D_max
                    # print 'Damage:', Damage
                    #print (time.time() - start_time), 'seconds of total simulation time'
                    break
                else:
                    D_med+=iterationstep

            #bearing calcs
            if self.availability != 0 and rotor_freq != 0 and T_life != 0 and V_f != 0 and weibullA != 0:
                N_rotations = self.availability*rotor_freq/60.*(T_life*365*24*60*60)*exp(-(V_0/weibullA)**weibullk)-exp(-(V_f/weibullA)**weibullk)
            elif np.max(n_Fx > 1e6):
                N_rotations = np.max(n_Fx)/blade_number
            elif np.max(n_My > 1e6):
                N_rotations = np.max(n_My)/blade_number
            # print 'Upwind bearing calcs'
            Fz1_Fz = Fz*(L_mb+L_rb)/L_mb
            Fz1_My = My/L_mb
            Fy1_Fy = -Fy*(L_mb+L_rb)/L_mb
            Fy1_Mz = Mz/L_mb
            [D_max_a,FW_max,bearing1mass] = fatigue2_for_bearings(D_max,self.mb1Type,np.zeros(2),np.array([1,2]),Fy1_Fy,n_Fy/blade_number,Fz1_Fz,n_Fz/blade_number,Fz1_My,n_My/blade_number,Fy1_Mz,n_Mz/blade_number,N_rotations)
            # print 'Downwind bearing calcs'
            Fz2_Fz = Fz*L_rb/L_mb
            Fz2_My = My/L_mb
            Fy2_Fy = Fy*L_rb/L_mb
            Fy2_Mz = Mz/L_mb
            [D_med_a,FW_med,bearing2mass] = fatigue2_for_bearings(D_med,self.mb2Type,Fx,n_Fx/blade_number,Fy2_Fy,n_Fy/blade_number,Fz2_Fz,n_Fz/blade_number,Fz2_My,n_My/blade_number,Fy2_Mz,n_Mz/blade_number,N_rotations)

        else: #if fatigue_check is not true, resize based on diameter
            [D_max_a,FW_max,bearing1mass] = resize_for_bearings(D_max,  self.mb1Type)
            [D_med_a,FW_med,bearing2mass] = resize_for_bearings(D_med,  self.mb2Type)

        # end fatigue code additions 6/2014
            
        lss_mass_new=(pi/3)*(D_max_a**2+D_med_a**2+D_max_a*D_med_a)*(L_mb-(FW_max+FW_med)/2)*density/4+ \
                         (pi/4)*(D_max_a**2-D_in**2)*density*FW_max+\
                         (pi/4)*(D_med_a**2-D_in**2)*density*FW_med-\
                         (pi/4)*(D_in**2)*density*(L_mb+(FW_max+FW_med)/2)

        ## begin bearing routine with updated shaft mass
        self.length=L_mb_new + (FW_max+FW_med)/2 + flange_length # add facewidths and flange
        # print ("L_mb: {0}").format(L_mb)
        # print ("LSS length, m: {0}").format(self.length)
        self.D_outer=D_max
        # print ("Upwind MB OD, m: {0}").format(D_max_a)
        # print ("Dnwind MB OD, m: {0}").format(D_med_a)
        # print ("D_min: {0}").format(D_min)
        self.D_in=D_in
        self.mass=lss_mass_new*1.33 # add flange mass
        self.diameter1= D_max_a
        self.diameter2= D_med_a 

        # calculate mass properties
        downwind_location = np.array([self.gearbox_cm[0]-self.gearbox_length/2. , self.gearbox_cm[1] , self.gearbox_cm[2] ])

        bearing_location1 = np.array([0.,0.,0.]) #upwind
        bearing_location1[0] = downwind_location[0] - (L_mb_new + FW_med/2)*cos(radians(gamma))
        bearing_location1[1] = downwind_location[1]
        bearing_location1[2] = downwind_location[2] + (L_mb_new + FW_med/2)*sin(radians(gamma))
        self.bearing_location1 = bearing_location1

        bearing_location2 = np.array([0.,0.,0.]) #downwind
        bearing_location2[0] = downwind_location[0] - FW_med*.5*cos(radians(gamma))
        bearing_location2[1] = downwind_location[1]
        bearing_location2[2] = downwind_location[2] + FW_med*.5*sin(radians(gamma))
        self.bearing_location2 = bearing_location2

        cm = np.array([0.0,0.0,0.0])
        cm[0] = downwind_location[0] - 0.65*self.length*cos(radians(gamma)) #From solid models, center of mass with flange (not including shrink disk) very nearly .65*total_length
        cm[1] = downwind_location[1]
        cm[2] = downwind_location[2] + 0.65*self.length*sin(radians(gamma))

        #including shrink disk mass
        self.cm[0] = (cm[0]*self.mass + downwind_location[0]*self.shrink_disc_mass) / (self.mass+self.shrink_disc_mass) 
        self.cm[1] = cm[1]
        self.cm[2] = (cm[2]*self.mass + downwind_location[2]*self.shrink_disc_mass) / (self.mass+self.shrink_disc_mass)
        self.mass+=self.shrink_disc_mass

        I = np.array([0.0, 0.0, 0.0])
        I[0]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0) / 8.0
        I[1]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0 + (4.0 / 3.0) * (self.length ** 2.0)) / 16.0
        I[2]  = I[1]
        self.I = I

        self.FW_mb1 = FW_max
        self.FW_mb2 = FW_med

        self.bearing_mass1 = bearing1mass
        self.bearing_mass2 = bearing2mass

#-------------------------------------------------------------------------------
class LowSpeedShaft_drive3pt(Component):
    ''' LowSpeedShaft class
          The LowSpeedShaft class is used to represent the low speed shaft component of a wind turbine drivetrain. 
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    # variables
    rotor_bending_moment_x = Float(iotype='in', units='N*m', desc='The bending moment about the x axis')
    rotor_bending_moment_y = Float(iotype='in', units='N*m', desc='The bending moment about the y axis')
    rotor_bending_moment_z = Float(iotype='in', units='N*m', desc='The bending moment about the z axis')
    rotor_force_x = Float(iotype='in', units='N', desc='The force along the x axis applied at hub center')
    rotor_force_y = Float(iotype='in', units='N', desc='The force along the y axis applied at hub center')
    rotor_force_z = Float(iotype='in', units='N', desc='The force along the z axis applied at hub center')
    rotor_mass = Float(iotype='in', units='kg', desc='rotor mass')
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    machine_rating = Float(iotype='in', units='kW', desc='machine_rating machine rating of the turbine')
    gearbox_mass = Float(iotype='in', units='kg', desc='Gearbox mass')
    carrier_mass = Float(iotype='in', units='kg', desc='Carrier mass')
    overhang = Float(iotype='in', units='m', desc='Overhang distance')

    # parameters
    shrink_disc_mass = Float(iotype='in', units='kg', desc='Mass of the shrink disc')
    gearbox_cm = Array(iotype = 'in', units = 'm', desc = 'center of mass of gearbox')
    gearbox_length = Float(iotype='in', units='m', desc='gearbox length')
    flange_length = Float(iotype ='in', units='m', desc ='flange length')
    shaft_angle = Float(iotype='in', units='deg', desc='Angle of the LSS inclindation with respect to the horizontal')
    shaft_ratio = Float(iotype='in', desc='Ratio of inner diameter to outer diameter.  Leave zero for solid LSS')
    mb1Type = Str(iotype='in',desc='Main bearing type: CARB, TRB1 or SRB')
    mb2Type = Str(iotype='in',desc='Second bearing type: CARB, TRB1 or SRB') 

    L_rb = Float(iotype='in', units='m', desc='distance between hub center and upwind main bearing')
    check_fatigue = Int(iotype = 'in', desc = 'turns on and off fatigue check')
    fatigue_exponent = Float(iotype = 'in', desc = 'fatigue exponent of material')
    S_ut = Float(iotype = 'in', units = 'Pa', desc = 'ultimate tensile strength of material')
    weibull_A = Float(iotype = 'in', units = 'm/s', desc = 'weibull scale parameter "A" of 10-minute windspeed probability distribution')
    weibull_k = Float(iotype = 'in', desc = 'weibull shape parameter "k" of 10-minute windspeed probability distribution')
    blade_number = Float(iotype = 'in', desc = 'number of blades on rotor, 2 or 3')
    cut_in = Float(iotype = 'in', units = 'm/s', desc = 'cut-in windspeed')
    cut_out = Float(iotype = 'in', units = 'm/s', desc = 'cut-out windspeed')
    Vrated = Float(iotype = 'in', units = 'm/s', desc = 'rated windspeed')
    T_life = Float(iotype = 'in', units = 'yr', desc = 'design life')
    IEC_Class = Str(iotype='in',desc='IEC class letter: A, B, or C')
    DrivetrainEfficiency = Float(iotype = 'in', desc = 'overall drivettrain efficiency')
    rotor_freq = Float(iotype = 'in', units = 'rpm', desc='rated rotor speed')
    availability = Float(.95,iotype = 'in', desc = 'turbine availability')

    rotor_thrust_distribution = Array(iotype='in', units ='N', desc = 'thrust distribution across turbine life')
    rotor_thrust_count = Array(iotype='in', desc = 'corresponding cycle array for thrust distribution')
    rotor_Fy_distribution = Array(iotype='in', units ='N', desc = 'Fy distribution across turbine life')
    rotor_Fy_count = Array(iotype='in', desc = 'corresponding cycle array for Fy distribution')
    rotor_Fz_distribution = Array(iotype='in', units ='N', desc = 'Fz distribution across turbine life')
    rotor_Fz_count = Array(iotype='in', desc = 'corresponding cycle array for Fz distribution') 
    rotor_torque_distribution = Array(iotype='in', units ='N*m', desc = 'torque distribution across turbine life')
    rotor_torque_count = Array(iotype='in', desc = 'corresponding cycle array for torque distribution') 
    rotor_My_distribution = Array(iotype='in', units ='N*m', desc = 'My distribution across turbine life')
    rotor_My_count = Array(iotype='in', desc = 'corresponding cycle array for My distribution') 
    rotor_Mz_distribution = Array(iotype='in', units ='N*m', desc = 'Mz distribution across turbine life')
    rotor_Mz_count = Array(iotype='in', desc = 'corresponding cycle array for Mz distribution') 
   
    # outputs
    design_torque = Float(iotype='out', units='N*m', desc='lss design torque')
    design_bending_load = Float(iotype='out', units='N', desc='lss design bending load')
    length = Float(iotype='out', units='m', desc='lss length')
    diameter1 = Float(iotype='out', units='m', desc='lss outer diameter at main bearing')
    diameter2 = Float(iotype='out', units='m', desc='lss outer diameter at second bearing')
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
    FW_mb = Float(iotype='out', units='m', desc='facewidth of main bearing')    
    bearing_mass1 = Float(iotype='out', units = 'kg', desc='main bearing mass')
    bearing_mass2 = Float(0., iotype='out', units = 'kg', desc='main bearing mass') #zero for 3-pt model
    bearing_location1 = Array(np.array([0,0,0]),iotype='out', units = 'm', desc = 'main bearing 1 center of mass')
    bearing_location2 = Array(np.array([0,0,0]),iotype='out', units = 'm', desc = 'main bearing 2 center of mass')

    def __init__(self):
        '''
        Initializes low speed shaft component  
        '''

        super(LowSpeedShaft_drive3pt, self).__init__()
    
    def execute(self):
        #Hub Forces
        F_r_x = self.rotor_force_x            #External F_x
        F_r_y = self.rotor_force_y                 #External F_y
        F_r_z = self.rotor_force_z                  #External F_z
        M_r_x = self.rotor_bending_moment_x
        M_r_y = self.rotor_bending_moment_y
        M_r_z = self.rotor_bending_moment_z

        #input parameters
        if self.flange_length ==0:
            flange_length = 0.9918*exp(.0068*self.rotor_diameter)
        else:
            flange_length = self.flange_length

        if self.L_rb == 0: #distance from hub center to main bearing
            L_rb = 0.007835*self.rotor_diameter+0.9642
        else:
            L_rb = self.L_rb

        gamma=self.shaft_angle #deg LSS angle wrt horizontal

        check_fatigue = self.check_fatigue
        blade_number = self.blade_number
        V_0 = self.cut_in
        V_f = self.cut_out
        V_rated = self.Vrated
        T_life =self.T_life
        IEC_Class_Letter = self.IEC_Class
        rotor_mass = self.rotor_mass
        rotor_diameter = self.rotor_diameter
        machine_rating = self.machine_rating
        rotor_freq = self.rotor_freq
        DrivetrainEfficiency = self.DrivetrainEfficiency

        g = 9.81 #m/s
        PSF = 1.0
        density = 7850.0


        L_ms_new = 0.0
        L_ms_0=0.5 # main shaft length downwind of main bearing
        L_ms=L_ms_0
        tol=1e-4 
        check_limit = 1.0
        dL=0.05
        D_max = 1.0
        D_min = 0.2
        sR = self.shaft_ratio
        # D_in=self.shaft_ratio*D_max
        rotor_diameter = self.rotor_diameter

        T=M_r_x/1000.0

        #Main bearing defelection check
        MB_limit=0.026;
        CB_limit=4.0/60.0/180.0*pi;
        TRB1_limit=3.0/60.0/180.0*pi;
        n_safety_brg = 1.0
        n_safety=2.5
        Sy = 66000.0 #psi
        E=2.1e11  
        N_count=50    
          
        u_knm_inlb = 8850.745454036
        u_in_m = 0.0254000508001
        counter=0
        length_max = self.overhang - self.L_rb + (self.gearbox_cm[0] -self.gearbox_length/2.) #modified length limit 7/29

        while abs(check_limit) > tol and L_ms_new < length_max:
            counter =counter+1
            if L_ms_new > 0:
                 L_ms=L_ms_new
            else:
                  L_ms=L_ms_0

            #Distances
            L_bg = 6.11 *(self.machine_rating/5.0e3)         #distance from hub center to gearbox yokes
            L_as = L_ms/2.0     #distance from main bearing to shaft center
            H_gb = 1.0          #distance to gbx center from trunnions in z-dir     
            L_gp = 0.825        #distance from gbx coupling to gbx trunnions
            L_cu = L_ms + 0.5
            L_cd = L_cu + 0.5
            L_gb=0

            #Weight properties
            weightRotor=0     # Yi modified to remove rotor overhung weight, considered in the load analysis                        #rotor weight accounted for in F_z
            massLSS = pi/3*(D_max**2.0 + D_min**2.0 + D_max*D_min)*L_ms*density/4.0
            weightLSS = massLSS*g       #LSS weight
            weightShrinkDisc = self.shrink_disc_mass*g                #shrink disc weight
            weightGbx = self.gearbox_mass*g                              #gearbox weight
            weightCarrier = self.carrier_mass*g

            len_pts=101;
            x_ms = np.linspace(L_rb, L_ms+L_rb, len_pts)
            x_rb = np.linspace(0.0, L_rb, len_pts)
            y_gp = np.linspace(0, L_gp, len_pts)

            #len_my = np.arange(1,len(M_r_y)+1)
            #print ("F_r_x: {0}").format(F_r_x)
            #print ("F_r_y: {0}").format(F_r_y)
            #print ("F_r_z: {0}").format(F_r_z)
            #print ("M_r_x: {0}").format(M_r_x)
            #print ("M_r_y: {0}").format(M_r_y)
            #print ("M_r_z: {0}").format(M_r_z)
            F_mb_x = -F_r_x - weightRotor*sin(radians(gamma))
            F_mb_y = M_r_z/L_bg - F_r_y*(L_bg + L_rb)/L_bg
            F_mb_z = (-M_r_y + weightRotor*(cos(radians(gamma))*(L_rb + L_bg)\
            + sin(radians(gamma))*H_gb) + weightLSS*(L_bg - L_as)\
            * cos(radians(gamma)) + weightShrinkDisc*cos(radians(gamma))\
            *(L_bg - L_ms) - weightGbx*cos(radians(gamma))*L_gb - F_r_z*cos(radians(gamma))*(L_bg + L_rb))/L_bg


            F_gb_x = -(weightLSS + weightShrinkDisc + weightGbx)*sin(radians(gamma))
            F_gb_y = -F_mb_y - F_r_y
            F_gb_z = -F_mb_z + (weightLSS + weightShrinkDisc + weightGbx + weightRotor)*cos(radians(gamma)) - F_r_z

            F_cu_z = (weightLSS*cos(radians(gamma)) + weightShrinkDisc*cos(radians(gamma)) + weightGbx*cos(radians(gamma))) - F_mb_z - F_r_z- \
            (-M_r_y - F_r_z*cos(radians(gamma))*L_rb + weightLSS*(L_bg - L_as)*cos(radians(gamma)) - weightCarrier*cos(radians(gamma))*L_gb)/(1 - L_cu/L_cd)

            F_cd_z = (weightLSS*cos(radians(gamma)) + weightShrinkDisc*cos(radians(gamma)) + weightGbx*cos(radians(gamma))) - F_mb_z - F_r_z - F_cu_z 


            My_ms = np.zeros(2*len_pts)
            Mz_ms = np.zeros(2*len_pts)

            for k in range(len_pts):
                My_ms[k] = -M_r_y + weightRotor*cos(radians(gamma))*x_rb[k] + 0.5*weightLSS/L_ms*x_rb[k]**2 - F_r_z*x_rb[k]
                Mz_ms[k] = -M_r_z - F_r_y*x_rb[k]

            for j in range(len_pts):
                My_ms[j+len_pts] = -F_r_z*x_ms[j] - M_r_y + weightRotor*cos(radians(gamma))*x_ms[j] - F_mb_z*(x_ms[j]-L_rb) + 0.5*weightLSS/L_ms*x_ms[j]**2
                Mz_ms[j+len_pts] = -M_r_z - F_mb_y*(x_ms[j]-L_rb) - F_r_y*x_ms[j]

            x_shaft = np.concatenate([x_rb, x_ms])

            MM_max=np.amax((My_ms**2 + Mz_ms**2)**0.5/1000.0)
            Index=np.argmax((My_ms**2 + Mz_ms**2)**0.5/1000.0)
                
            #print 'Max Moment kNm:'
            #print MM_max
            #print 'Max moment location m:'
            #print x_shaft[Index]

            MM_min = ((My_ms[-1]**2+Mz_ms[-1]**2)**0.5/1000.0)

            #print 'Max Moment kNm:'
            #print MM_min
            #print 'Max moment location m:'#
            #print x_shaft[-1]

            #Design shaft OD using distortion energy theory
            
           
            MM=MM_max
            D_max=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb)**2 + 3.0*(M_r_x/1000.0*u_knm_inlb)**2)**0.5)**(1.0/3.0)*u_in_m

            #OD at end
            MM=MM_min
            D_min=(16.0*n_safety/pi/Sy*(4.0*(MM*u_knm_inlb)**2 + 3.0*(M_r_x/1000.0*u_knm_inlb)**2)**0.5)**(1.0/3.0)*u_in_m

            #Estimate ID
            D_in=self.shaft_ratio*D_max
            D_max=(D_in**4.0 + D_max**4.0)**0.25
            D_min=(D_in**4.0 + D_min**4.0)**0.25
            #print'Max shaft OD m:'
            #print D_max
            #print 'Min shaft OD m:'
            #print D_min
            #print'Shaft ID:', D_in
            

            weightLSS_new = (density*pi/12.0*L_ms*(D_max**2.0 + D_min**2.0 + D_max*D_min) - density*pi/4.0*D_in**2.0*L_ms + \
                              density*pi/4.0*D_max**2*L_rb)*g
            massLSS_new = weightLSS_new/g

            #print 'Old LSS mass kg:' 
            #print massLSS
            #print 'New LSS mass kg:'
            #print massLSS_new

            def fx(F_r_z,W_r,gamma,M_r_y,f_mb_z,L_rb,W_ms,L_ms,z):
                return -F_r_z*z**3/6.0 + W_r*cos(radians(gamma))*z**3/6.0 - M_r_y*z**2/2.0 - f_mb_z*(z-L_rb)**3/6.0 + W_ms/(L_ms + L_rb)/24.0*z**4
            
                       
            D1 = fx(F_r_z,weightRotor,gamma,M_r_y,F_mb_z,L_rb,weightLSS_new,L_ms,L_rb+L_ms)
            D2 = fx(F_r_z,weightRotor,gamma,M_r_y,F_mb_z,L_rb,weightLSS_new,L_ms,L_rb)
            C1 = -(D1-D2)/L_ms;
            C2 = -D2-C1*(L_rb);
            
            
            I_2=pi/64.0*(D_max**4 - D_in**4)

            def gx(F_r_z,W_r,gamma,M_r_y,f_mb_z,L_rb,W_ms,L_ms,C1,z):
                return -F_r_z*z**2/2.0 + W_r*cos(radians(gamma))*z**2/2.0 - M_r_y*z - f_mb_z*(z-L_rb)**2/2.0 + W_ms/(L_ms + L_rb)/6.0*z**3 + C1

            theta_y = np.zeros(len_pts)
            d_y = np.zeros(len_pts)

            for kk in range(len_pts):
                theta_y[kk]=gx(F_r_z,weightRotor,gamma,M_r_y,F_mb_z,L_rb,weightLSS_new,L_ms,C1,x_ms[kk])/E/I_2
                d_y[kk]=(fx(F_r_z,weightRotor,gamma,M_r_y,F_mb_z,L_rb,weightLSS_new,L_ms,x_ms[kk])+C1*x_ms[kk]+C2)/E/I_2

            check_limit = abs(abs(theta_y[-1])-TRB1_limit/n_safety_brg)
            #print 'deflection slope'
            #print TRB1_limit
            #print 'threshold'
            #print theta_y[-1]
            L_ms_new = L_ms + dL        

        # fatigue check Taylor Parsons 6/2014
        if check_fatigue == 1 or 2:
          #start_time = time.time()

          g=9.81 
          #material properties 34CrNiMo6 steel +QT, large diameter
          E=2.1e11
          density=7800.0
          n_safety = 2.5
          Sy = 490.0e6 # Pa
          if self.S_ut > 0:
            Sut = self.S_ut
          else:
            Sut=700.0e6 #Pa
          Sm=0.9*Sut #for bending situations, material strength at 10^3 cycles
          C_size=0.6 #diameter larger than 10"
          C_surf=4.51*(Sut/1e6)**-.265 #machined surface 272*(Sut/1e6)**-.995 #forged
          C_temp=1 #normal operating temps
          C_reliab=0.814 #99% reliability
          C_envir=1. #enclosed environment
          Se=C_size*C_surf*C_temp*C_reliab*C_envir*.5*Sut #modified endurance limit for infinite life

          if self.fatigue_exponent!=0:
            SN_b = -1/self.fatigue_exponent
          else:
            Nfinal = 5e8 #point where fatigue limit occurs under hypothetical S-N curve TODO adjust to fit actual data
            z=log10(1e3)-log10(Nfinal)  #assuming no endurance limit (high strength steel)
            SN_b=1/z*log10(Sm/Se)
          SN_a=Sm/(1000.**SN_b)
          # print 'm:', -1/SN_b
          # print 'a:', SN_a

          #Weibull Parameters
          weibullA=self.weibull_A
          weibullk=self.weibull_k

          if check_fatigue == 1:
              #checks to make sure all inputs are reasonable
              if rotor_mass < 100:
                  rotor_mass = get_rotor_mass(self.machine_rating)

              #Rotor Loads calculations using DS472
              R=rotor_diameter/2.0
              rotor_torque = (machine_rating * 1000 / DrivetrainEfficiency) / (rotor_freq * (pi/30))
              Tip_speed_ratio= rotor_freq/30.*pi*R/V_rated
              rho_air= 1.225 #kg/m^3 density of air
              p_o = 4./3*rho_air*((4*pi*rotor_freq/60*R/3)**2+V_rated**2)*(pi*R/(blade_number*Tip_speed_ratio*(Tip_speed_ratio**2+1)**(.5)))

              n_c=blade_number*rotor_freq/60 #characteristic frequency on rotor from turbine of given blade number [Hz]
              N_f=self.availability*n_c*(T_life*365*24*60*60)*exp(-(V_0/weibullA)**weibullk)-exp(-(V_f/weibullA)**weibullk) #number of rotor rotations based off of weibull curve. .827 comes from lower rpm than rated at lower wind speeds


              k_b= 2.5 #calculating rotor pressure from all three blades. Use kb=1 for individual blades

              if IEC_Class_Letter == 'A': # From IEC 61400-1 TODO consider calculating based off of 10-minute windspeed and weibull parameters, include neighboring wake effects?
                I_t=0.18 
              elif IEC_Class_Letter == 'B':
                I_t=0.14
              else:
                I_t=0.12

              Beta=0.11*k_b*(I_t+0.1)*(weibullA+4.4)

              # find generic standardized stochastic load range distribution
              def standardrange(N, N_f, Beta, k_b): 
                  F_delta=(Beta*(log10(N_f)-log10(N)))+0.18
                  if F_delta>=2*k_b:
                    F_delta=0.
                  return F_delta

              def rounddown(x,step):
                return int(floor(x/step))*step

              def roundup(x,step):
                  return int(ceil(x/step))*step

              #for analysis with N on log scale, makes larger loads contain finer step sizes
              num_pts=100
              N=np.logspace( (log10(N_f)-(2*k_b-0.18)/Beta) , log10(N_f) , endpoint=True , num=num_pts) # with zeros: N=np.logspace(log10(1.0),log10(N_f),endpoint=True,num=num_pts)
              N_rotor = N_f/3.
              F_stoch=N.copy()


              for i in range(num_pts):
                  N[i]=roundup(N[i],1)

              #print N

              k_r=0.8 #assuming natural frequency of rotor is significantly larger than rotor rotational frequency

              for i in range(num_pts):
                F_stoch[i] = standardrange(N[i],N_f,Beta,k_b)

              Fx_factor = (.3649*log(rotor_diameter)-1.074)
              Mx_factor = (.0799*log(rotor_diameter)-.2577)
              My_factor = (.172*log(rotor_diameter)-.5943)
              Mz_factor = (.1659*log(rotor_diameter)-.5795)

              Fx_stoch = (F_stoch.copy()*0.5*p_o*(R))*Fx_factor #divide by 2 to reflect amplitudes?
              Mx_stoch = (F_stoch.copy()*0.45*p_o*(R)**2)*Mx_factor#*0.31
              My_stoch = (F_stoch.copy()*0.33*p_o*k_r*(R)**2)*My_factor#*.5*0.25
              Mz_stoch = (F_stoch.copy()*0.33*p_o*k_r*(R)**2)*Mz_factor#*.5*0.25 

              def Ninterp(S,a,b):
                  return (S/a)**(1/b)

              def Goodman(S_alt,S_mean,Sut):
                  return S_alt/(1-(S_mean/Sut))

              Fx_mean=0.5*p_o*R*blade_number*Fx_factor
              Mx_mean=0.5*rotor_torque*Mx_factor
              rotorWeight=rotor_mass*g

              # print 'Fx_max:', np.max(Fx_stoch) + Fx_mean
              # print 'Mx_max:', np.max(Mx_stoch) + Mx_mean
              # print 'My_max:', np.max(My_stoch)
              # print 'Mz_max:', np.max(Mz_stoch)
              # print 'occurance:', np.min(N)

              #upwind bearing calculations
              iterationstep=0.01
              diameter_limit = 1.5
              while True:
                  D_in=sR*D_max
                  D_max = (D_max**4 + D_in**4)**0.25
                  D_min = (D_min**4 + D_in**4)**0.25
                  I=(pi/64.0)*(D_max**4-D_in**4)
                  J=I*2
                  Area=pi/4.*(D_max**2-D_in**2)
                  LssWeight=density*9.81*(((pi/12)*(D_max**2+D_min**2+D_max*D_min)*(L_ms))-(pi/4*L_ms*D_in**2))

                  #create stochastic loads across N
                  stoch_bend1 = (My_stoch**2+Mz_stoch**2)**(0.5)*D_max/(2.*I)
                  stoch_shear1 = abs(Mx_stoch*D_max/(2.*J))
                  stoch_normal1 = Fx_stoch/Area*cos(radians(gamma))
                  stoch_stress1 = ((stoch_bend1+stoch_normal1)**2+3.*stoch_shear1**2)**(0.5)
                  
                  #create mean loads
                  mean_bend1 = 0 #Fz_mean*L_rb*D_max/(2.*I) #not mean, but deterministic
                  mean_shear1 = Mx_mean*D_max/(2.*J)
                  mean_normal1 = Fx_mean/Area*cos(radians(gamma))+(rotorWeight+LssWeight)*sin(radians(gamma))
                  mean_stress1 = ((mean_bend1+mean_normal1)**2+3.*mean_shear1**2)**(0.5)

                  #apply Goodman with compressive (-) mean stress
                  S_mod_stoch1=Goodman(stoch_stress1,-mean_stress1,Sut)

                  #Use Palmgren-Miner linear damage rule to add damage from stochastic load ranges
                  DEL_y=Fx_stoch.copy() #initialize
                  for i in range(num_pts):
                      DEL_y[i] = N[i]/(Ninterp(S_mod_stoch1[i],SN_a,SN_b))

                  Damage = scp.integrate.simps(DEL_y,x= N, even='avg') #damage from stochastic loading

                  #create deterministic loads occurring N_rotor times
                  determ_stress1 = abs(rotorWeight*cos(radians(gamma))*L_rb*D_max/(2.*I)) #only deterministic stress at mb1 is bending due to weights

                  S_mod_determ=Goodman(determ_stress1,-mean_stress1,Sut)
                  # print 'before deterministic Damage:', Damage

                  Damage += N_rotor/(Ninterp(S_mod_determ,SN_a,SN_b))

                  # print 'Bearing Diameter:', D_max
                  # print 'Damage:', Damage
                  if Damage < 1 or D_max >= diameter_limit:
                      # print 'Bearing Diameter:', D_max
                      # print 'Damage:', Damage
                      #print (time.time() - start_time), 'seconds of total simulation time'
                      break
                  else:
                      D_max+=iterationstep

              #begin bearing calculations
              N_bearings = N/blade_number #rotation number

              Fz1stoch = (-My_stoch)/(L_ms)
              Fy1stoch = Mz_stoch/L_ms
              Fz1determ = (weightGbx*L_gb - LssWeight*.5*L_ms - rotorWeight*(L_ms+L_rb)) / (L_ms)

              Fr_range = ((abs(Fz1stoch)+abs(Fz1determ))**2 +Fy1stoch**2)**.5 #radial stochastic + deterministic mean
              Fa_range = Fx_stoch*cos(radians(gamma)) + (rotorWeight+LssWeight)*sin(radians(gamma)) #axial stochastic + mean

              life_bearing = N_f/blade_number

              [D_max_a,FW_max,bearingmass] = fatigue_for_bearings(D_max, Fr_range, Fa_range, N_bearings, life_bearing, self.mb1Type)

          elif check_fatigue == 2:
            Fx = self.rotor_thrust_distribution
            n_Fx = self.rotor_thrust_count
            Fy = self.rotor_Fy_distribution
            n_Fy = self.rotor_Fy_count
            Fz = self.rotor_Fz_distribution
            n_Fz = self.rotor_Fz_count
            Mx = self.rotor_torque_distribution
            n_Mx = self.rotor_torque_count
            My = self.rotor_My_distribution
            n_My = self.rotor_My_count
            Mz = self.rotor_Mz_distribution
            n_Mz = self.rotor_Mz_count

            # print n_Fx
            # print Fx*.5
            # print Mx*.5
            # print -1/SN_b

            def Ninterp(L_ult,L_range,m):
                return (L_ult/(.5*L_range))**m #TODO double-check that the input will be the load RANGE instead of load amplitudes. Also, may include means?

            #upwind bearing calcs
            diameter_limit = 5.0
            iterationstep=0.01
            #upwind bearing calcs
            while True:
                Damage = 0
                Fx_ult = SN_a*(pi/4.*(D_max**2-D_in**2))
                Fyz_ult = SN_a*(pi*(D_max**4-D_in**4))/(D_max*32*L_rb)
                Mx_ult = SN_a*(pi*(D_max**4-D_in**4))/(32*(3.**.5)*D_max)
                Myz_ult = SN_a*(pi*(D_max**4-D_in**4))/(D_max*64.)
                if Fx_ult and np.all(n_Fx):
                    Damage+=scp.integrate.simps(n_Fx/Ninterp(Fx_ult,Fx,-1/SN_b),x=n_Fx,even = 'avg')
                if Fyz_ult:
                    if np.all(n_Fy):
                        Damage+=scp.integrate.simps(abs(n_Fy/Ninterp(Fyz_ult,Fy,-1/SN_b)),x=n_Fy,even = 'avg')
                    if np.all(n_Fz):
                        Damage+=scp.integrate.simps(abs(n_Fz/Ninterp(Fyz_ult,Fz,-1/SN_b)),x=n_Fz,even = 'avg')
                if Mx_ult and np.all(n_Mx):
                    Damage+=scp.integrate.simps(abs(n_Mx/Ninterp(Mx_ult,Mx,-1/SN_b)),x=n_Mx,even = 'avg')
                if Myz_ult:
                    if np.all(n_My):
                        Damage+=scp.integrate.simps(abs(n_My/Ninterp(Myz_ult,My,-1/SN_b)),x=n_My,even = 'avg')
                    if np.all(n_Mz):
                        Damage+=scp.integrate.simps(abs(n_Mz/Ninterp(Myz_ult,Mz,-1/SN_b)),x=n_Mz,even = 'avg')

                print 'Upwind Bearing Diameter:', D_max
                print 'Damage:', Damage

                if Damage <= 1 or D_max >= diameter_limit:
                    # print 'Upwind Bearing Diameter:', D_max
                    # print 'Damage:', Damage
                    #print (time.time() - start_time), 'seconds of total simulation time'
                    break
                else:
                    D_max+=iterationstep

            #bearing calcs
            if self.availability != 0 and rotor_freq != 0 and T_life != 0 and V_f != 0 and weibullA != 0:
                N_rotations = self.availability*rotor_freq/60.*(T_life*365*24*60*60)*exp(-(V_0/weibullA)**weibullk)-exp(-(V_f/weibullA)**weibullk)
            elif np.max(n_Fx > 1e6):
                N_rotations = np.max(n_Fx)/blade_number
            elif np.max(n_My > 1e6):
                N_rotations = np.max(n_My)/blade_number

            # Fz1 = (Fz*(L_ms+L_rb)+My)/L_ms
            Fz1_Fz = Fz*(L_ms+L_rb)/L_ms #force in z direction due to Fz
            Fz1_My = My/L_ms #force in z direction due to My
            Fy1_Fy = -Fy*(L_ms+L_rb)/L_ms
            Fy1_Mz = Mz/L_ms
            [D_max_a,FW_max,bearingmass] = fatigue2_for_bearings(D_max,self.mb1Type,np.zeros(2),np.array([1,2]),Fy1_Fy,n_Fy/blade_number,Fz1_Fz,n_Fz/blade_number,Fz1_My,n_My/blade_number,Fy1_Mz,n_Mz/blade_number,N_rotations)
         
        #resize bearing if no fatigue check
        if check_fatigue == 0:
            [D_max_a,FW_max,bearingmass] = resize_for_bearings(D_max,  self.mb1Type)

        [D_min_a,FW_min,trash] = resize_for_bearings(D_min,  self.mb2Type) #mb2 is a representation of the gearbox connection
            
        lss_mass_new=(pi/3)*(D_max_a**2+D_min_a**2+D_max_a*D_min_a)*(L_ms-(FW_max+FW_min)/2)*density/4+ \
                         (pi/4)*(D_max_a**2-D_in**2)*density*FW_max+\
                         (pi/4)*(D_min_a**2-D_in**2)*density*FW_min-\
                         (pi/4)*(D_in**2)*density*(L_ms+(FW_max+FW_min)/2)
        lss_mass_new *= 1.35 # add flange and shrink disk mass
        self.length=L_ms_new + (FW_max+FW_min)/2 + flange_length
        #print ("L_ms: {0}").format(L_ms)
        #print ("LSS length, m: {0}").format(self.length)
        self.D_outer=D_max
        #print ("Upwind MB OD, m: {0}").format(D_max_a)
        #print ("CB OD, m: {0}").format(D_min_a)
        #print ("D_min: {0}").format(D_min)
        self.D_in=D_in
        self.mass=lss_mass_new
        self.diameter1= D_max_a
        self.diameter2= D_min_a 
        #self.length=L_ms
        #print self.length
        self.D_outer=D_max_a
        self.diameter=D_max_a

         # calculate mass properties
        downwind_location = np.array([self.gearbox_cm[0]-self.gearbox_length/2. , self.gearbox_cm[1] , self.gearbox_cm[2] ])

        bearing_location1 = np.array([0.,0.,0.]) #upwind
        bearing_location1[0] = downwind_location[0] - L_ms*cos(radians(gamma))
        bearing_location1[1] = downwind_location[1]
        bearing_location1[2] = downwind_location[2] + L_ms*sin(radians(gamma))
        self.bearing_location1 = bearing_location1

        self.bearing_location2 = np.array([0.,0.,0.]) #downwind does not exist

        cm = np.array([0.0,0.0,0.0])
        cm[0] = downwind_location[0] - 0.65*self.length*cos(radians(gamma)) #From solid models, center of mass with flange (not including shrink disk) very nearly .65*total_length
        cm[1] = downwind_location[1]
        cm[2] = downwind_location[2] + 0.65*self.length*sin(radians(gamma))

        #including shrink disk mass
        self.cm[0] = (cm[0]*self.mass + downwind_location[0]*self.shrink_disc_mass) / (self.mass+self.shrink_disc_mass) 
        self.cm[1] = cm[1]
        self.cm[2] = (cm[2]*self.mass + downwind_location[2]*self.shrink_disc_mass) / (self.mass+self.shrink_disc_mass)
        # print 'shaft before shrink disk:', self.mass
        self.mass+=self.shrink_disc_mass

        I = np.array([0.0, 0.0, 0.0])
        I[0]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0) / 8.0
        I[1]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0 + (4.0 / 3.0) * (self.length ** 2.0)) / 16.0
        I[2]  = I[1]
        self.I = I

        # print 'L_rb %8.f' %(L_rb) #*(self.machine_rating/5.0e3)   #distance from hub center to main bearing scaled off NREL 5MW
        # print 'L_bg %8.f' %(L_bg) #*(self.machine_rating/5.0e3)         #distance from hub center to gearbox yokes
        # print 'L_as %8.f' %(L_as) #distance from main bearing to shaft center
      
        self.FW_mb=FW_max
        self.bearing_mass1 = bearingmass
        self.bearing_mass2 = 0.

#-------------------------------------------------------------------------------

class LowSpeedShaft_drive(Component):
    ''' LowSpeedShaft class
          The LowSpeedShaft class is used to represent the low speed shaft component of a wind turbine drivetrain. This model is outdated and does not contain fatigue analysis
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    # variables
    rotor_torque = Float(iotype='in', units='N*m', desc='The torque load due to aerodynamic forces on the rotor')
    rotor_bending_moment = Float(iotype='in', units='N*m', desc='The bending moment from uneven aerodynamic loads')
    rotor_mass = Float(iotype='in', units='kg', desc='rotor mass')
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    rotor_speed = Float(iotype='in', units='rpm', desc='rotor speed at rated power')
    machine_rating = Float(iotype='in', units='kW', desc='machine_rating machine rating of the turbine')

    # parameters
    shaft_angle = Float(iotype='in', units='deg', desc='Angle of the LSS inclindation with respect to the horizontal')
    shaft_length = Float(iotype='in', units='m', desc='length of low speed shaft')
    shaftD1 = Float(iotype='in', units='m', desc='Fraction of LSS distance from gearbox to downwind main bearing')
    shaftD2 = Float(iotype='in', units='m', desc='raction of LSS distance from gearbox to upwind main bearing')
    shaft_ratio = Float(iotype='in', desc='Ratio of inner diameter to outer diameter.  Leave zero for solid LSS')
    
    # outputs
    design_torque = Float(iotype='out', units='N*m', desc='lss design torque')
    design_bending_load = Float(iotype='out', units='N', desc='lss design bending load')
    length = Float(iotype='out', units='m', desc='lss length')
    diameter = Float(iotype='out', units='m', desc='lss outer diameter')
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    

    def __init__(self):
        '''
        Initializes low speed shaft component
        '''

        super(LowSpeedShaft_drive, self).__init__()
    
    def execute(self):    

        def calc_mass(rotor_torque, rotor_bending_moment, rotor_mass, rotorDiaemeter, rotor_speed, shaft_angle, shaft_length, shaftD1, shaftD2, machine_rating, shaft_ratio):
        
                # Second moment of area for hollow shaft
            def Imoment(d_o,d_i):
                I=(pi/64.0)*(d_o**4-d_i**4)
                return I
            
            # Second polar moment for hollow shaft
            def Jmoment(d_o,d_i):
                J=(pi/32.0)*(d_o**4-d_i**4)
                return J
            
            # Bending stress
            def bendingStress(M, y, I):
                sigma=M*y/I
                return sigma
            
            # Shear stress
            def shearStress(T, r, J):
                tau=T*r/J
                return tau
            
            #Find the necessary outer diameter given a diameter ratio and max stress
            def outerDiameterStrength(shaft_ratio,maxFactoredStress):
                D_outer=(16.0/(pi*(1.0-shaft_ratio**4.0)*maxFactoredStress)*(factoredTotalRotorMoment+sqrt(factoredTotalRotorMoment**2.0+factoredrotor_torque**2.0)))**(1.0/3.0)
                return D_outer

            #[rotor_torque, rotor_bending_moment, rotor_mass, rotorDiaemeter, rotor_speed, shaft_angle, shaft_length, shaftD1, shaftD2, machine_rating, shaft_ratio] = x

            #torque check
            if rotor_torque == 0:
                omega=rotor_speed/60*(2*pi)      #rotational speed in rad/s at rated power
                eta=0.944                 #drivetrain efficiency
                rotor_torque=machine_rating/(omega*eta)         #torque

            #self.length=shaft_length
                
            # compute masses, dimensions and cost
            #static overhanging rotor moment (need to adjust for CM of rotor not just distance to end of LSS)
            L2=shaft_length*shaftD2                   #main bearing to end of mainshaft
            alpha=shaft_angle*pi/180.0           #shaft angle
            L2=L2*cos(alpha)                  #horizontal distance from main bearing to hub center of mass
            staticRotorMoment=rotor_mass*L2*9.81      #static bending moment from rotor
          
            #assuming 38CrMo4 / AISI 4140 from http://www.efunda.com/materials/alloys/alloy_steels/show_alloy.cfm?id=aisi_4140&prop=all&page_title=aisi%204140
            yieldStrength=417.0*10.0**6.0 #Pa
            steelDensity=8.0*10.0**3
            
            #Safety Factors
            gammaAero=1.35
            gammaGravity=1.35 #some talk of changing this to 1.1
            gammaFavorable=0.9
            gammaMaterial=1.25 #most conservative
            
            maxFactoredStress=yieldStrength/gammaMaterial
            factoredrotor_torque=rotor_torque*gammaAero
            factoredTotalRotorMoment=rotor_bending_moment*gammaAero-staticRotorMoment*gammaFavorable

            self.D_outer=outerDiameterStrength(self.shaft_ratio,maxFactoredStress)
            self.D_in=shaft_ratio*self.D_outer

            #print "LSS outer diameter is %f m, inner diameter is %f m" %(self.D_outer, self.D_in)
            
            J=Jmoment(self.D_outer,self.D_in)
            I=Imoment(self.D_outer,self.D_in)
            
            sigmaX=bendingStress(factoredTotalRotorMoment, self.D_outer/2.0, I)
            tau=shearStress(rotor_torque, self.D_outer/2.0, J)
            
            #print "Max unfactored normal bending stress is %g MPa" % (sigmaX/1.0e6)
            #print "Max unfactored shear stress is %g MPa" % (tau/1.0e6)
            
            volumeLSS=((self.D_outer/2.0)**2.0-(self.D_in/2.0)**2.0)*pi*shaft_length
            mass=volumeLSS*steelDensity
            
            return mass
        
        self.mass = calc_mass(self.rotor_torque, self.rotor_bending_moment, self.rotor_mass, self.rotor_diameter, self.rotor_speed, \
                                    self.shaft_angle, self.shaft_length, self.shaftD1, self.shaftD2, self.machine_rating, self.shaft_ratio)
        

        self.design_torque = self.rotor_torque
        self.design_bending_load = self.rotor_bending_moment
        self.length = self.shaft_length
        self.diameter = self.D_outer

        # calculate mass properties
        cm = np.array([0.0,0.0,0.0])
        cm[0] = - (0.035 - 0.01) * self.rotor_diameter            # cm based on WindPACT work - halfway between locations of two main bearings
        cm[1] = 0.0
        cm[2] = 0.025 * self.rotor_diameter
        self.cm = cm

        I = np.array([0.0, 0.0, 0.0])
        I[0]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0) / 8.0
        I[1]  = self.mass * (self.D_in ** 2.0 + self.D_outer ** 2.0 + (4.0 / 3.0) * (self.length ** 2.0)) / 16.0
        I[2]  = I[1]
        self.I = I

#-------------------------------------------------------------------------------

class Bearing_drive(Component): 
    ''' MainBearings class          
          The MainBearings class is used to represent the main bearing components of a wind turbine drivetrain. It contains two subcomponents (main bearing and second bearing) which also inherit from the SubComponent class.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.           
    '''
    # variables
    bearing_type = Str(iotype='in',desc='Main bearing type: CARB, TRB1 or SRB')
    bearing_mass = Float(iotype ='in', units = 'kg', desc = 'bearing mass from LSS model')
    lss_diameter = Float(iotype='in', units='m', desc='lss outer diameter at main bearing')
    lss_design_torque = Float(iotype='in', units='N*m', desc='lss design torque')
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    location = Array(np.array([0.,0.,0.]),iotype = 'in', units = 'm', desc = 'x,y,z location from shaft model')


    
    # returns
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
    
    def __init__(self):
        
        super(Bearing_drive, self).__init__()
    
    def execute(self):
        self.mass = self.bearing_mass
        self.mass += self.mass*(8000.0/2700.0) #add housing weight

class MainBearing_drive(Bearing_drive): 
    ''' MainBearings class          
          The MainBearings class is used to represent the main bearing components of a wind turbine drivetrain. It contains two subcomponents (main bearing and second bearing) which also inherit from the SubComponent class.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.           
    '''
    
    def __init__(self):
        ''' Initializes main bearing component 
        '''
        
        super(MainBearing_drive, self).__init__()
    
    def execute(self):

        super(MainBearing_drive, self).execute()
        
        # calculate mass properties
        inDiam  = self.lss_diameter
        depth = (inDiam * 1.5)

        if self.location[0] != 0.0:
            self.cm = self.location

        else:
            cmMB = np.array([0.0,0.0,0.0])
            cmMB = ([- (0.035 * self.rotor_diameter), 0.0, 0.025 * self.rotor_diameter])
            self.cm = cmMB
       
        b1I0 = (self.mass * inDiam ** 2 ) / 4.0 
        self.I = ([b1I0, b1I0 / 2.0, b1I0 / 2.0])

#-------------------------------------------------------------------------------

class SecondBearing_drive(Bearing_drive): 
    ''' MainBearings class          
          The MainBearings class is used to represent the main bearing components of a wind turbine drivetrain. It contains two subcomponents (main bearing and second bearing) which also inherit from the SubComponent class.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.           
    '''
    
    def __init__(self):
        ''' Initializes second bearing component 
        '''
        
        super(SecondBearing_drive, self).__init__()
    
    def execute(self):

        super(SecondBearing_drive, self).execute()

        # calculate mass properties
        inDiam  = self.lss_diameter
        depth = (inDiam * 1.5)

        if self.mass > 0 and self.location[0] != 0.0:
            self.cm = self.location
        elif self.mass >0:
            cmSB = np.array([0.0,0.0,0.0])
            cmSB = ([- (0.01 * self.rotor_diameter), 0.0, 0.025 * self.rotor_diameter])
            self.cm = cmSB
        else:
            self.cm = np.array([0,0,0])
            self.mass = 0.


        b2I0  = (self.mass * inDiam ** 2 ) / 4.0 
        self.I = ([b2I0, b2I0 / 2.0, b2I0 / 2.0])

#-------------------------------------------------------------------------------


class Gearbox_drive(Component):
    ''' Gearbox class
          The Gearbox class is used to represent the gearbox component of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    #variables
    
    gear_ratio = Float(iotype='in', desc='overall gearbox speedup ratio')
    Np = Array(np.array([0.0,0.0,0.0,]), iotype='in', desc='number of planets in each stage')
    rotor_speed = Float(iotype='in', desc='rotor rpm at rated power')
    rotor_diameter = Float(iotype='in', desc='rotor diameter')
    rotor_torque = Float(iotype='in', units='N*m', desc='rotor torque at rated power')
    cm_input = Float(0,iotype = 'in', units='m', desc ='gearbox position along x-axis')

    #parameters
    #name = Str(iotype='in', desc='gearbox name')
    gear_configuration = Str(iotype='in', desc='string that represents the configuration of the gearbox (stage number and types)')
    #eff = Float(iotype='in', desc='drivetrain efficiency')
    ratio_type = Str(iotype='in', desc='optimal or empirical stage ratios')
    shaft_type = Str(iotype='in', desc = 'normal or short shaft length')

    # outputs
    stage_masses = Array(np.array([0.0, 0.0, 0.0, 0.0]), iotype='out', units='kg', desc='individual gearbox stage masses')
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    
    length = Float(iotype='out', units='m', desc='gearbox length')
    height = Float(iotype='out', units='m', desc='gearbox height')
    diameter = Float(iotype='out', units='m', desc='gearbox diameter')


    def __init__(self):
        '''
        Initializes gearbox component
        '''



        super(Gearbox_drive,self).__init__()

    def execute(self):

        self.stageRatio=np.zeros([3,1])

        self.stageTorque = np.zeros([len(self.stageRatio),1]) #filled in when ebxWeightEst is called
        self.stageMass = np.zeros([len(self.stageRatio),1]) #filled in when ebxWeightEst is called
        self.stageType=self.stageTypeCalc(self.gear_configuration)
        #print self.gear_ratio
        #print self.Np
        #print self.ratio_type
        #print self.gear_configuration
        self.stageRatio=self.stageRatioCalc(self.gear_ratio,self.Np,self.ratio_type,self.gear_configuration)
        #print self.stageRatio

        m=self.gbxWeightEst(self.gear_configuration,self.gear_ratio,self.Np,self.ratio_type,self.shaft_type,self.rotor_torque)
        self.mass = float(m)
        self.stage_masses=self.stageMass
        # calculate mass properties

        self.length = (0.012 * self.rotor_diameter)
        self.height = (0.015 * self.rotor_diameter)
        self.diameter = (0.75 * self.height)

        cm0   = self.cm_input
        cm1   = 0.0
        cm2   = 0.4*self.height #TODO validate or adjust factor. origin is modified to be above bedplate top
        self.cm = np.array([cm0, cm1, cm2])

        I0 = self.mass * (self.diameter ** 2 ) / 8 + (self.mass / 2) * (self.height ** 2) / 8
        I1 = self.mass * (0.5 * (self.diameter ** 2) + (2 / 3) * (self.length ** 2) + 0.25 * (self.height ** 2)) / 8
        I2 = I1
        self.I = np.array([I0, I1, I2])

        '''def rotor_torque():
            tq = self.gbxPower*1000 / self.eff / (self.rotor_speed * (pi / 30.0))
            return tq
        '''
     
    def stageTypeCalc(self, config):
        temp=[]
        for character in config:
                if character == 'e':
                    temp.append(2)
                if character == 'p':
                    temp.append(1)
        return temp

    def stageMassCalc(self, indStageRatio,indNp,indStageType):

        '''
        Computes the mass of an individual gearbox stage.

        Parameters
        ----------
        indStageRatio : str
          Speedup ratio of the individual stage in question.
        indNp : int
          Number of planets for the individual stage.
        indStageType : int
          Type of gear.  Use '1' for parallel and '2' for epicyclic.
        '''

        #Application factor to include ring/housing/carrier weight
        Kr=0.4
        Kgamma=1.1

        if indNp == 3:
            Kgamma=1.1
        elif indNp == 4:
            Kgamma=1.1
        elif indNp == 5:
            Kgamma=1.35

        if indStageType == 1:
            indStageMass=1.0+indStageRatio+indStageRatio**2+(1.0/indStageRatio)

        elif indStageType == 2:
            sunRatio=0.5*indStageRatio - 1.0
            indStageMass=Kgamma*((1/indNp)+(1/(indNp*sunRatio))+sunRatio+sunRatio**2+Kr*((indStageRatio-1)**2)/indNp+Kr*((indStageRatio-1)**2)/(indNp*sunRatio))

        return indStageMass
        
    def gbxWeightEst(self, config,overallRatio,Np,ratio_type,shaft_type,torque):


        '''
        Computes the gearbox weight based on a surface durability criteria.
        '''

        ## Define Application Factors ##
        #Application factor for weight estimate
        Ka=0.6
        Kshaft=0.0
        Kfact=0.0

        #K factor for pitting analysis
        if self.rotor_torque < 200000.0:
            Kfact = 850.0
        elif self.rotor_torque < 700000.0:
            Kfact = 950.0
        else:
            Kfact = 1100.0

        #Unit conversion from Nm to inlb and vice-versa
        Kunit=8.029

        # Shaft length factor
        if self.shaft_type == 'normal':
            Kshaft = 1.0
        elif self.shaft_type == 'short':
            Kshaft = 1.25

        #Individual stage torques
        torqueTemp=self.rotor_torque
        for s in range(len(self.stageRatio)):
            #print torqueTemp
            #print self.stageRatio[s]
            self.stageTorque[s]=torqueTemp/self.stageRatio[s]
            torqueTemp=self.stageTorque[s]
            self.stageMass[s]=Kunit*Ka/Kfact*self.stageTorque[s]*self.stageMassCalc(self.stageRatio[s],self.Np[s],self.stageType[s])
        
        gbxWeight=(sum(self.stageMass))*Kshaft
        
        return gbxWeight

    def stageRatioCalc(self, overallRatio,Np,ratio_type,config):
        '''
        Calculates individual stage ratios using either empirical relationships from the Sunderland model or a SciPy constrained optimization routine.
        '''

        K_r=0
                    
        #Assumes we can model everything w/Sunderland model to estimate speed ratio
        if ratio_type == 'empirical':
            if config == 'p': 
                x=[overallRatio]
            if config == 'e':
                x=[overallRatio]
            elif config == 'pp':
                x=[overallRatio**0.5,overallRatio**0.5]
            elif config == 'ep':
                x=[overallRatio/2.5,2.5]
            elif config =='ee':
                x=[overallRatio**0.5,overallRatio**0.5]
            elif config == 'eep':
                x=[(overallRatio/3)**0.5,(overallRatio/3)**0.5,3]
            elif config == 'epp':
                x=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
            elif config == 'eee':
                x=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
            elif config == 'ppp':
                x=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
        
        elif ratio_type == 'optimal':
            x=np.zeros([3,1])

            if config == 'eep':
                x0=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
                B_1=Np[0]
                B_2=Np[1]
                K_r1=0
                K_r2=0 #2nd stage structure weight coefficient

                def volume(x):
                    return (1.0/(x[0]))*((1.0/B_1)+(1.0/(B_1*((x[0]/2.0)-1.0)))+(x[0]/2.0-1.0)+ \
                    (x[0]/2.0-1)**2+K_r1*((x[0]-1.0)**2)/B_1 + K_r1*((x[0]-1.0)**2)/(B_1*(x[0]/2.0-1.0))) + \
                    (1.0/(x[0]*x[1]))*((1.0/B_2)+(1/(B_2*((x[1]/2.0)-1.0)))+(x[1]/2.0-1.0)+(x[1]/2.0-1.0)**2.0+K_r2*((x[1]-1.0)**2.0)/B_2 + \
                     K_r2*((x[1]-1.0)**2.0)/(B_2*(x[1]/2.0-1.0))) + (1.0/(x[0]*x[1]*x[2]))*(1.0+(1.0/x[2])+x[2] + x[2]**2)                              
                
                def constr1(x,overallRatio):
                    return x[0]*x[1]*x[2]-overallRatio
        
                def constr2(x,overallRatio):
                    return overallRatio-x[0]*x[1]*x[2]

                x=opt.fmin_cobyla(volume, x0,[constr1,constr2],consargs=[overallRatio],rhoend=1e-7, iprint = 0)
        
            elif config == 'eep_3':
                #fixes last stage ratio at 3
                x0=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
                B_1=Np[0]
                B_2=Np[1]
                K_r1=0
                K_r2=0.8 #2nd stage structure weight coefficient

                def volume(x):
                    return (1.0/(x[0]))*((1.0/B_1)+(1.0/(B_1*((x[0]/2.0)-1.0)))+(x[0]/2.0-1.0)+(x[0]/2.0-1)**2+K_r1*((x[0]-1.0)**2)/B_1 + K_r1*((x[0]-1.0)**2)/(B_1*(x[0]/2.0-1.0))) + (1.0/(x[0]*x[1]))*((1.0/B_2)+(1/(B_2*((x[1]/2.0)-1.0)))+(x[1]/2.0-1.0)+(x[1]/2.0-1.0)**2.0+K_r2*((x[1]-1.0)**2.0)/B_2 + K_r2*((x[1]-1.0)**2.0)/(B_2*(x[1]/2.0-1.0))) + (1.0/(x[0]*x[1]*x[2]))*(1.0+(1.0/x[2])+x[2] + x[2]**2)                              
                
                def constr1(x,overallRatio):
                    return x[0]*x[1]*x[2]-overallRatio
        
                def constr2(x,overallRatio):
                    return overallRatio-x[0]*x[1]*x[2]
                
                def constr3(x,overallRatio):
                    return x[2]-3.0
                
                def constr4(x,overallRatio):
                    return 3.0-x[2]

                x=opt.fmin_cobyla(volume, x0,[constr1,constr2,constr3,constr4],consargs=[overallRatio],rhoend=1e-7,iprint=0)
            
            elif config == 'eep_2':
                #fixes final stage ratio at 2
                x0=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
                B_1=Np[0]
                B_2=Np[1]
                K_r1=0
                K_r2=1.6 #2nd stage structure weight coefficient

                def volume(x):
                    return (1.0/(x[0]))*((1.0/B_1)+(1.0/(B_1*((x[0]/2.0)-1.0)))+(x[0]/2.0-1.0)+(x[0]/2.0-1)**2+K_r1*((x[0]-1.0)**2)/B_1 + K_r1*((x[0]-1.0)**2)/(B_1*(x[0]/2.0-1.0))) + (1.0/(x[0]*x[1]))*((1.0/B_2)+(1/(B_2*((x[1]/2.0)-1.0)))+(x[1]/2.0-1.0)+(x[1]/2.0-1.0)**2.0+K_r2*((x[1]-1.0)**2.0)/B_2 + K_r2*((x[1]-1.0)**2.0)/(B_2*(x[1]/2.0-1.0))) + (1.0/(x[0]*x[1]*x[2]))*(1.0+(1.0/x[2])+x[2] + x[2]**2)                              
                
                def constr1(x,overallRatio):
                    return x[0]*x[1]*x[2]-overallRatio
        
                def constr2(x,overallRatio):
                    return overallRatio-x[0]*x[1]*x[2]

                x=opt.fmin_cobyla(volume, x0,[constr1,constr2],consargs=[overallRatio],rhoend=1e-7, iprint = 0)
            elif config == 'epp':
                #fixes last stage ratio at 3
                x0=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
                B_1=Np[0]
                B_2=Np[1]
                K_r=0
               
                def volume(x):
                    return (1.0/(x[0]))*((1.0/B_1)+(1.0/(B_1*((x[0]/2.0)-1.0)))+(x[0]/2.0-1.0)+(x[0]/2.0-1)**2+ \
                    K_r*((x[0]-1.0)**2)/B_1 + K_r*((x[0]-1.0)**2)/(B_1*(x[0]/2.0-1.0))) + \
                    (1.0/(x[0]*x[1]))*(1.0+(1.0/x[1])+x[1] + x[1]**2) \
                    + (1.0/(x[0]*x[1]*x[2]))*(1.0+(1.0/x[2])+x[2] + x[2]**2)                              
                
                def constr1(x,overallRatio):
                    return x[0]*x[1]*x[2]-overallRatio
        
                def constr2(x,overallRatio):
                    return overallRatio-x[0]*x[1]*x[2]
                
                x=opt.fmin_cobyla(volume, x0,[constr1,constr2],consargs=[overallRatio],rhoend=1e-7,iprint=0)
                
            else:  # what is this subroutine for?  Yi on 04/16/2014
                x0=[overallRatio**(1.0/3.0),overallRatio**(1.0/3.0),overallRatio**(1.0/3.0)]
                B_1=Np[0]
                K_r=0.0
                def volume(x):
                    return (1.0/(x[0]))*((1.0/B_1)+(1.0/(B_1*((x[0]/2.0)-1.0)))+(x[0]/2.0-1)+(x[0]/2.0-1.0)**2+K_r*((x[0]-1.0)**2)/B_1 + K_r*((x[0]-1)**2)/(B_1*(x[0]/2.0-1.0))) + (1.0/(x[0]*x[1]))*(1.0+(1.0/x[1])+x[1] + x[1]**2)+ (1.0/(x[0]*x[1]*x[2]))*(1.0+(1.0/x[2])+x[2] + x[2]**2)
                                  
                def constr1(x,overallRatio):
                   return x[0]*x[1]*x[2]-overallRatio
        
                def constr2(x,overallRatio):
                    return overallRatio-x[0]*x[1]*x[2]

                x=opt.fmin_cobyla(volume, x0,[constr1,constr2],consargs=[overallRatio],rhoend=1e-7, iprint = 0)
        else:
            x='fail'
                  
        return x
        
#---------------------------------------------------------------------------------------------------------------

class Bedplate_drive(Component):
    ''' Bedplate class
          The Bedplate class is used to represent the bedplate of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    #variables
    gbx_length = Float(iotype = 'in', units = 'm', desc = 'gearbox length')
    gbx_location = Float(iotype = 'in', units = 'm', desc = 'gearbox CM location')
    gbx_mass = Float(iotype = 'in', units = 'kg', desc = 'gearbox mass')
    hss_location = Float(iotype ='in', units = 'm', desc='HSS CM location')
    hss_mass = Float(iotype ='in', units = 'kg', desc='HSS mass')
    generator_location = Float(iotype ='in', units = 'm', desc='generator CM location')
    generator_mass = Float(iotype ='in', units = 'kg', desc='generator mass')
    lss_location = Float(iotype ='in', units = 'm', desc='LSS CM location')
    lss_mass = Float(iotype ='in', units = 'kg', desc='LSS mass')
    lss_length = Float(iotype = 'in', units = 'm', desc = 'LSS length')
    mb1_location = Float(iotype ='in', units = 'm', desc='Upwind main bearing CM location')
    FW_mb1 = Float(iotype = 'in', units = 'm', desc = 'Upwind main bearing facewidth')
    mb1_mass = Float(iotype ='in', units = 'kg', desc='Upwind main bearing mass')
    mb2_location = Float(iotype ='in', units = 'm', desc='Downwind main bearing CM location')
    mb2_mass = Float(iotype ='in', units = 'kg', desc='Downwind main bearing mass')
    transformer_mass = Float(iotype ='in', units = 'kg', desc='Transformer mass')
    transformer_location = Float(iotype = 'in', units = 'm', desc = 'transformer CM location')
    tower_top_diameter = Float(iotype ='in', units = 'm', desc='diameter of the top tower section at the yaw gear')
    rotor_diameter = Float(iotype = 'in', units = 'm', desc='rotor diameter')
    machine_rating = Float(iotype='in', units='kW', desc='machine_rating machine rating of the turbine')
    rotor_mass = Float(iotype='in', units='kg', desc='rotor mass')
    rotor_bending_moment_y = Float(iotype='in', units='N*m', desc='The bending moment about the y axis')
    rotor_force_z = Float(iotype='in', units='N', desc='The force along the z axis applied at hub center')
    flange_length = Float(iotype='in', units='m', desc='flange length')
    L_rb = Float(iotype = 'in', units = 'm', desc = 'length between rotor center and upwind main bearing')
    overhang = Float(iotype='in', units='m', desc='Overhang distance')

    #parameters
    uptower_transformer = Bool(iotype = 'in', desc = 'Boolean stating if transformer is uptower')

    #outputs
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    
    length = Float(iotype='out', units='m', desc='length of bedplate')
    height = Float(iotype='out', units='m', desc='max height of bedplate')
    width = Float(iotype='out', units='m', desc='width of bedplate')

    def __init__(self):
        ''' Initializes bedplate component
        '''

        super(Bedplate_drive,self).__init__()

    def execute(self):
        #Model bedplate as 2 parallel I-beams with a rear steel frame and a front cast frame
        #Deflection constraints applied at each bedplate end
        #Stress constraint checked at root of front and rear bedplate sections

        g = 9.81
        E = 2.1e11
        density = 7800

        if self.L_rb:
            L_rb = self.L_rb
        else:
            L_rb = 0.007835*self.rotor_diameter+0.9642

        #component weights and locations
        if self.transformer_mass: #only if uptower transformer
            transLoc = self.transformer_location
            convMass = 0.3*self.transformer_mass
        else:
            transLoc = 0
            convMass = (2.4445*(self.machine_rating) + 1599.0)*0.3 #(transformer mass * .3)

        convLoc = self.generator_location * 2.0
        mb1_location = abs(self.mb1_location) #abs(self.gbx_length/2.0) + abs(self.lss_length)
        mb2_location = abs(self.mb2_location) #abs(self.gbx_length/2.0)
        lss_location= abs(self.lss_location)

        if transLoc > 0:
          rearTotalLength = transLoc*1.1
        else:
          rearTotalLength = self.generator_location*4.237/2.886 -self.tower_top_diameter/2.0 #scaled off of GE1.5

        frontTotalLength = mb1_location + self.FW_mb1/2.

        #rotor weights and loads
        rotorLoc = mb1_location + L_rb
        rotorFz=abs(self.rotor_force_z)
        rotorMy=abs(self.rotor_bending_moment_y)

        #initial I-beam dimensions
        tf = 0.01905
        tw = 0.0127
        h0 = 0.6096
        b0 = h0/2.0

        def midDeflection(totalLength,loadLength,load,E,I):
          defl = load*loadLength**2.0*(3.0*totalLength - loadLength)/(6.0*E*I)
          return defl

          #tip deflection for distributed load
        def distDeflection(totalLength,distWeight,E,I):
          defl = distWeight*totalLength**4.0/(8.0*E*I)
          return defl

        
        #Rear Steel Frame:
        if self.gbx_location > 0:
            gbx_location = self.gbx_location
            gbx_mass = self.gbx_mass
        else: 
            gbx_location = 0
            gbx_mass = 0

        rootStress = 250e6
        totalTipDefl = 1.0
        stressTol = 5e5
        deflTol = 1e-4
        counter = 0
        defl_denom = 1000 #factor in deflection check
        stress_mult = 6 #modified to fit industry data

        stressMax = 620e6 #yeild of alloy steel
        deflMax = rearTotalLength/defl_denom

        while rootStress*stress_mult - stressMax >  stressTol or totalTipDefl - deflMax >  deflTol:
          counter += 1
          bi = (b0-tw)/2.0
          hi = h0-2.0*tf
          I = b0*h0**3/12.0 - 2*bi*hi**3/12.0
          A = b0*h0 - 2.0*bi*hi
          w=A*density
          #Tip Deflection for load not at end
          
          hssTipDefl = midDeflection(rearTotalLength,self.hss_location,self.hss_mass*g/2,E,I)
          genTipDefl = midDeflection(rearTotalLength,self.generator_location,self.generator_mass*g/2,E,I)
          convTipDefl = midDeflection(rearTotalLength,convLoc,convMass*g/2,E,I)
          transTipDefl = midDeflection(rearTotalLength,transLoc,self.transformer_mass*g/2,E,I)
          gbxTipDefl = midDeflection(rearTotalLength,gbx_location,gbx_mass*g/2,E,I)
          selfTipDefl = distDeflection(rearTotalLength,w*g,E,I)

          totalTipDefl = hssTipDefl + genTipDefl + convTipDefl + transTipDefl +  selfTipDefl + gbxTipDefl
          
          #root stress
          totalBendingMoment=(self.hss_location*self.hss_mass + self.generator_location*self.generator_mass + convLoc*convMass + transLoc*self.transformer_mass + w*rearTotalLength**2/2.0)*g
          rootStress = totalBendingMoment*h0/(2.*I)

          #mass
          steelVolume = A*rearTotalLength
          steelMass = steelVolume*density

          #2 parallel I beams
          totalSteelMass = 2.0*steelMass

          rearTotalTipDefl=totalTipDefl
          rearBendingStress=rootStress

          tf += 0.002 
          tw += 0.002
          b0 += 0.006
          h0 += 0.006

          rearCounter = counter

        rearHeight = h0

        #Front cast section:
        if self.gbx_location < 0:
            gbx_location = abs(self.gbx_location)
            gbx_mass = self.gbx_mass
        else: 
            gbx_location = 0
            gbx_mass = 0
        E=169e9 #EN-GJS-400-18-LT http://www.claasguss.de/html_e/pdf/THBl2_engl.pdf
        castDensity = 7100

        tf = 0.01905
        tw = 0.0127
        h0 = 0.6096
        b0 = h0/2.0

        rootStress = 250e6
        totalTipDefl = 1.0
        counter = 0

        deflMax = frontTotalLength/defl_denom
        stressMax = 200e6

        while rootStress*stress_mult - stressMax >  stressTol or totalTipDefl - deflMax >  deflTol:
          counter += 1
          bi = (b0-tw)/2.0
          hi = h0-2.0*tf
          I = b0*h0**3/12.0 - 2*bi*hi**3/12.0
          A = b0*h0 - 2.0*bi*hi
          w=A*castDensity

          #Tip Deflection for load not at end
          gbxTipDefl = midDeflection(frontTotalLength,gbx_mass,gbx_mass*g/2.0,E,I)
          mb1TipDefl = midDeflection(frontTotalLength,mb1_location,self.mb1_mass*g/2.0,E,I)
          mb2TipDefl = midDeflection(frontTotalLength,mb2_location,self.mb2_mass*g/2.0,E,I)
          lssTipDefl = midDeflection(frontTotalLength,lss_location,self.lss_mass*g/2.0,E,I)
          rotorTipDefl = midDeflection(frontTotalLength,rotorLoc,self.rotor_mass*g/2.0,E,I)
          rotorFzTipDefl = midDeflection(frontTotalLength,rotorLoc,rotorFz/2.0,E,I)
          selfTipDefl = distDeflection(frontTotalLength,w*g,E,I)
          rotorMyTipDefl = rotorMy/2.0*frontTotalLength**2/(2.0*E*I)

          totalTipDefl = mb1TipDefl + mb2TipDefl + lssTipDefl  + rotorTipDefl + selfTipDefl +rotorMyTipDefl + rotorFzTipDefl + gbxTipDefl

          #root stress
          totalBendingMoment=(mb1_location*self.mb1_mass/2.0 + mb2_location*self.mb2_mass/2.0 + lss_location*self.lss_mass/2.0 + w*frontTotalLength**2/2.0 + rotorLoc*self.rotor_mass/2.0)*g + rotorLoc*rotorFz/2.0 +rotorMy/2.0
          rootStress = totalBendingMoment*h0/2/I

          #mass
          castVolume = A*frontTotalLength
          castMass = castVolume*castDensity

          #2 parallel I-beams
          totalCastMass = 2.0*castMass


          frontTotalTipDefl=totalTipDefl
          frontBendingStress=rootStress

          tf += 0.002 
          tw += 0.002
          b0 += 0.006
          h0 += 0.006

          frontCounter=counter

        frontHeight = h0

        #frame multiplier for front support
        support_multiplier = 1.1+5e13*self.rotor_diameter**(-8) # based on solidworks estimates for GRC and GE bedplates. extraneous mass percentage decreases for larger machines
        # print self.rotor_diameter
        # print support_multiplier
        totalCastMass *= support_multiplier
        totalSteelMass *= support_multiplier
        self.mass = totalCastMass+ totalSteelMass

        # print 'rotor mass', self.rotor_mass
        # print 'rotor bending moment_y', self.rotor_bending_moment_y
        # print 'rotor fz', self.rotor_force_z 
        # print 'rear bedplate length: ', rearTotalLength
        # print 'front bedplate length: ', frontTotalLength
        # print'rear bedplate tip deflection', rearTotalTipDefl
        # print'front bedplate tip deflection', frontTotalTipDefl
        # print 'bending stress [MPa] at root of rear bedplate:', rearBendingStress/1.0e6
        # print 'bending stress [MPa] at root of front bedplate:', frontBendingStress/1.0e6
        # print 'front bedplate bedplate mass [kg]:', totalCastMass
        # print 'rear bedplate mass [kg]:', totalSteelMass
        # print 'total bedplate mass:', totalSteelMass+ totalCastMass

        self.length = frontTotalLength + rearTotalLength
        self.width = b0 + self.tower_top_diameter
        if rearHeight >= frontHeight:
            self.height = rearHeight
        else:
            self.height = frontHeight

        # calculate mass properties
        cm = np.array([0.0,0.0,0.0])
        cm[0] = (totalSteelMass*rearTotalLength/2 - totalCastMass*frontTotalLength/2)/(self.mass) #previously 0.
        cm[1] = 0.0
        cm[2] = -self.height/2.
        self.cm = cm

        self.depth = (self.length / 2.0)

        I = np.array([0.0, 0.0, 0.0])
        I[0]  = self.mass * (self.width ** 2 + self.depth ** 2) / 8
        I[1]  = self.mass * (self.depth ** 2 + self.width ** 2 + (4/3) * self.length ** 2) / 16
        I[2]  = I[1]
        self.I = I
        
        # print 'front length and mass:', frontTotalLength, totalCastMass
        # print 'rear length and mass:', rearTotalLength, totalSteelMass 
        
#---------------------------------------------------------------------------------------------------------------

class YawSystem_drive(Component):
    ''' YawSystem class
          The YawSystem class is used to represent the yaw system of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    #variables
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    rotor_thrust = Float(iotype='in', units='N', desc='maximum rotor thrust')
    tower_top_diameter = Float(iotype='in', units='m', desc='tower top diameter')
    above_yaw_mass = Float(iotype='in', units='kg', desc='above yaw mass')
    bedplate_height = Float(iotype = 'in', units = 'm', desc = 'bedplate height')

    #parameters
    yaw_motors_number = Int(0,iotype='in', desc='number of yaw motors')

    #outputs
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    


    def __init__(self):
        ''' Initializes yaw system
        '''
        super(YawSystem_drive, self).__init__()

    def execute(self):
        
        if self.yaw_motors_number == 0 :
          if self.rotor_diameter < 90.0 :
            self.yaw_motors_number = 4
          elif self.rotor_diameter < 120.0 :
            self.yaw_motors_number = 6
          else:
            self.yaw_motors_number = 8

        #Assume friction plate surface width is 1/10 the diameter
        #Assume friction plate thickness scales with rotor diameter
        frictionPlateVol=pi*self.tower_top_diameter*(self.tower_top_diameter*0.10)*(self.rotor_diameter/1000.0)
        steelDensity=8000.0
        frictionPlateMass=frictionPlateVol*steelDensity
        
        #Assume same yaw motors as Vestas V80 for now: Bonfiglioli 709T2M
        yawMotorMass=190.0
        
        totalYawMass=frictionPlateMass + (self.yaw_motors_number*yawMotorMass)
        self.mass= totalYawMass

        # calculate mass properties
        # yaw system assumed to be collocated to tower top center
        cm = np.array([0.0,0.0,0.0])
        cm[2] = -self.bedplate_height
        self.cm = cm

        # assuming 0 MOI for yaw system (ie mass is nonrotating)
        I = np.array([0.0, 0.0, 0.0])
        self.I = I

        #-------------------------------------------------------------------------------

class Transformer_drive(Component):
    ''' Transformer class
            The transformer class is used to represent the transformer of a wind turbine drivetrain.
            It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
            It contains an update method to determine the mass, mass properties, and dimensions of the component if it is in fact uptower'''

    #inputs
    machine_rating = Float(iotype='in', units='kW', desc='machine rating of the turbine')
    uptower_transformer = Bool(iotype='in', desc = 'uptower or downtower transformer')
    tower_top_diameter = Float(iotype = 'in', units = 'm', desc = 'tower top diameter for comparision of nacelle CM')
    rotor_mass = Float(iotype='in', units='kg', desc='rotor mass')
    overhang = Float(iotype='in', units='m', desc='rotor overhang distance')
    generator_cm = Array(iotype='in', desc='center of mass of the generator in [x,y,z]')
    rotor_diameter = Float(iotype='in',units='m', desc='rotor diameter of turbine')
    RNA_mass = Float(iotype = 'in', units='kg', desc='mass of total RNA')
    RNA_cm = Float(iotype='in', units='m', desc='RNA CM along x-axis')

    #outputs
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')    

    def __init__(self):
        '''
        Initializes transformer component
        '''

        super(Transformer_drive, self).__init__()

        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        def combine_CM(mass1,CM1,mass2,CM2):
            return (mass1*CM1+mass2*CM2)/(mass1+mass2)

        if self.uptower_transformer == True:
            #function places transformer where tower top CM is within tower bottom OD to reduce tower moments
            if self.rotor_mass:
                rotor_mass = self.rotor_mass
            else:
                rotor_mass = get_rotor_mass(self.machine_rating)

            bottom_OD = self.tower_top_diameter*1.7 #approximate average from industry data
            # print bottom_OD

            self.mass = 2.4445*(self.machine_rating) + 1599.0

            if self.RNA_cm <= -(bottom_OD)/2: #upwind of acceptable. Most likely
                transformer_x = (bottom_OD/2.*(self.RNA_mass+self.mass) - (self.RNA_mass*self.RNA_cm))/(self.mass)
                if transformer_x > self.generator_cm[0]*3:
                    print '\n ---------transformer location manipulation not suitable for overall Nacelle CM changes: rear distance excessively large------- \n'
                    transformer_x = self.generator_cm[0] + (1.6 * 0.015 * self.rotor_diameter) #assuming generator and transformer approximately same length
            else:
                transformer_x = self.generator_cm[0] + (1.8 * 0.015 * self.rotor_diameter) #assuming generator and transformer approximately same length

            cm = np.array([0.,0.,0.])
            cm[0] = transformer_x
            cm[1] = self.generator_cm[1]
            cm[2] = self.generator_cm[2]/.75*.5 #same height as gearbox CM
            self.cm = cm

            width = self.tower_top_diameter+.5
            height = 0.016*self.rotor_diameter #similar to gearbox
            length = .012*self.rotor_diameter #similar to gearbox

            def get_I(d1,d2,mass):
                return mass*(d1**2 + d2**2)/12.

            I = np.array([0.,0.,0.])
            I[0] = get_I(height,width,self.mass)
            I[1] = get_I(length, height, self.mass)
            I[2] = get_I(length, width, self.mass)
            self.I = I


        else:
            self.cm = np.array([0.,0.,0.])
            self.I = self.cm.copy()
            self.mass = 0.


#-------------------------------------------------------------------

class HighSpeedSide_drive(Component):
    '''
    HighSpeedShaft class
          The HighSpeedShaft class is used to represent the high speed shaft and mechanical brake components of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    # variables
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    rotor_torque = Float(iotype='in', units='N*m', desc='rotor torque at rated power')
    gear_ratio = Float(iotype='in', desc='overall gearbox ratio')
    lss_diameter = Float(iotype='in', units='m', desc='low speed shaft outer diameter')
    gearbox_length = Float(iotype = 'in', units = 'm', desc='gearbox length')
    gearbox_height = Float(iotype='in', units = 'm', desc = 'gearbox height')
    gearbox_cm = Array(iotype = 'in', units = 'm', desc = 'gearbox cm [x,y,z]')
    length_in = Float(iotype = 'in', units = 'm', desc = 'high speed shaft length determined by user. Default 0.5m')

    # returns
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')
    length = Float(iotype='out', desc='length of high speed shaft')

    def __init__(self):
        '''
        Initializes high speed side component
        '''

        super(HighSpeedSide_drive, self).__init__()

        #controls what happens if derivatives are missing
        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        # compute masses, dimensions and cost
        design_torque = self.rotor_torque / self.gear_ratio               # design torque [Nm] based on rotor torque and Gearbox ratio
        massFact = 0.025                                 # mass matching factor default value
        highSpeedShaftMass = (massFact * design_torque)

        mechBrakeMass = (0.5 * highSpeedShaftMass)      # relationship derived from HSS multiplier for University of Sunderland model compared to NREL CSM for 750 kW and 1.5 MW turbines

        self.mass = (mechBrakeMass + highSpeedShaftMass)

        diameter = (1.5 * self.lss_diameter)                     # based on WindPACT relationships for full HSS / mechanical brake assembly
        if self.length_in == 0:
            self.length = 0.5+self.rotor_diameter/127.
        else:
            self.length = self.length_in
        length = self.length

        matlDensity = 7850. # material density kg/m^3

        # calculate mass properties
        cm = np.array([0.0,0.0,0.0])
        cm[0]   = self.gearbox_cm[0]+self.gearbox_length/2+length/2
        cm[1]   = self.gearbox_cm[1]
        cm[2]   = self.gearbox_cm[2]+self.gearbox_height*0.2
        self.cm = cm

        I = np.array([0.0, 0.0, 0.0])
        I[0]    = 0.25 * length * 3.14159 * matlDensity * (diameter ** 2) * (self.gear_ratio**2) * (diameter ** 2) / 8.
        I[1]    = self.mass * ((3/4.) * (diameter ** 2) + (length ** 2)) / 12.
        I[2]    = I[1]
        self.I = I

#----------------------------------------------------------------------------------------------

class Generator_drive(Component):
    '''Generator class
          The Generator class is used to represent the generator of a wind turbine drivetrain.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''

    # variables
    rotor_diameter = Float(iotype='in', units='m', desc='rotor diameter')
    machine_rating = Float(iotype='in', units='kW', desc='machine rating of generator')
    gear_ratio = Float(iotype='in', desc='overall gearbox ratio')
    highSpeedSide_length = Float( iotype = 'in', units = 'm', desc='length of high speed shaft and brake')
    highSpeedSide_cm = Array(np.array([0.0,0.0,0.0]), iotype = 'in', units = 'm', desc='cm of high speed shaft and brake')
    rotor_speed = Float(iotype='in', units='rpm', desc='Speed of rotor at rated power')

    # parameters
    drivetrain_design = Enum('geared', ('geared', 'single_stage', 'multi_drive', 'pm_direct_drive'), iotype='in')

    # returns
    mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    cm = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    I = Array(np.array([0.0, 0.0, 0.0]), iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')

    def __init__(self):
        '''
        Initializes generator component
        '''

        super(Generator_drive, self).__init__()

        #controls what happens if derivatives are missing
        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        massCoeff = [None, 6.4737, 10.51 ,  5.34  , 37.68  ]
        massExp   = [None, 0.9223, 0.9223,  0.9223, 1      ]

        if self.rotor_speed !=0:
          CalcRPM = self.rotor_speed
        else:
          CalcRPM    = 80 / (self.rotor_diameter*0.5*pi/30)
        CalcTorque = (self.machine_rating*1.1) / (CalcRPM * pi/30)

        if self.drivetrain_design == 'geared':
            drivetrain_design = 1
        elif self.drivetrain_design == 'single_stage':
            drivetrain_design = 2
        elif self.drivetrain_design == 'multi_drive':
            drivetrain_design = 3
        elif self.drivetrain_design == 'pm_direct_drive':
            drivetrain_design = 4

        if (drivetrain_design < 4):
            self.mass = (massCoeff[drivetrain_design] * self.machine_rating ** massExp[drivetrain_design])
        else:  # direct drive
            self.mass = (massCoeff[drivetrain_design] * CalcTorque ** massExp[drivetrain_design])

        # calculate mass properties
        length = (1.8 * 0.015 * self.rotor_diameter)
        depth = (0.015 * self.rotor_diameter)
        width = (0.5 * depth)

        # print self.highSpeedSide_cm
        cm = np.array([0.0,0.0,0.0])
        cm[0]  = self.highSpeedSide_cm[0] + self.highSpeedSide_length/2. + length/2.
        cm[1]  = self.highSpeedSide_cm[1]
        cm[2]  = self.highSpeedSide_cm[2]
        self.cm = cm

        I = np.array([0.0, 0.0, 0.0])
        I[0]   = ((4.86 * (10. ** (-5))) * (self.rotor_diameter ** 5.333)) + (((2./3.) * self.mass) * (depth ** 2 + width ** 2) / 8.)
        I[1]   = (I[0] / 2.) / (self.gear_ratio ** 2) + ((1./3.) * self.mass * (length ** 2) / 12.) + (((2. / 3.) * self.mass) * \
                   (depth ** 2. + width ** 2. + (4./3.) * (length ** 2.)) / 16. )
        I[2]   = I[1]
        self.I = I

#-------------------------------------------------------------------------------

class AboveYawMassAdder_drive(Component):

    # variables
    machine_rating = Float(iotype = 'in', units='kW', desc='machine rating')
    lss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    main_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    second_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    gearbox_mass = Float(iotype = 'in', units='kg', desc='component mass')
    hss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    generator_mass = Float(iotype = 'in', units='kg', desc='component mass')
    bedplate_mass = Float(iotype = 'in', units='kg', desc='component mass')
    bedplate_length = Float(iotype = 'in', units='m', desc='component length')
    bedplate_width = Float(iotype = 'in', units='m', desc='component width')

    # parameters
    crane = Bool(iotype='in', desc='flag for presence of crane')

    # returns
    electrical_mass = Float(iotype = 'out', units='kg', desc='component mass')
    vs_electronics_mass = Float(iotype = 'out', units='kg', desc='component mass')
    hvac_mass = Float(iotype = 'out', units='kg', desc='component mass')
    controls_mass = Float(iotype = 'out', units='kg', desc='component mass')
    platforms_mass = Float(iotype = 'out', units='kg', desc='component mass')
    crane_mass = Float(iotype = 'out', units='kg', desc='component mass')
    mainframe_mass = Float(iotype = 'out', units='kg', desc='component mass')
    cover_mass = Float(iotype = 'out', units='kg', desc='component mass')
    above_yaw_mass = Float(iotype = 'out', units='kg', desc='total mass above yaw system')
    length = Float(iotype = 'out', units='m', desc='component length')
    width = Float(iotype = 'out', units='m', desc='component width')
    height = Float(iotype = 'out', units='m', desc='component height')

    def __init__(self):
        ''' Initialize above yaw mass adder component
        '''

        super(AboveYawMassAdder_drive, self).__init__()

        #controls what happens if derivatives are missing
        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        # electronic systems, hydraulics and controls
        self.electrical_mass = 0.0

        self.vs_electronics_mass = 0 #2.4445*self.machine_rating + 1599.0 accounted for in transformer calcs

        self.hvac_mass = 0.08 * self.machine_rating

        self.controls_mass     = 0.0

        # mainframe system including bedplate, platforms, crane and miscellaneous hardware
        self.platforms_mass = 0.125 * self.bedplate_mass

        if (self.crane):
            self.crane_mass =  3000.0
        else:
            self.crane_mass = 0.0

        self.mainframe_mass  = self.bedplate_mass + self.crane_mass + self.platforms_mass

        nacelleCovArea      = 2 * (self.bedplate_length ** 2)              # this calculation is based on Sunderland
        self.cover_mass = (84.1 * nacelleCovArea) / 2          # this calculation is based on Sunderland - divided by 2 in order to approach CSM

        # yaw system weight calculations based on total system mass above yaw system
        self.above_yaw_mass =  self.lss_mass + \
                    self.main_bearing_mass + self.second_bearing_mass + \
                    self.gearbox_mass + \
                    self.hss_mass + \
                    self.generator_mass + \
                    self.mainframe_mass + \
                    self.electrical_mass + \
                    self.vs_electronics_mass + \
                    self.hvac_mass + \
                    self.cover_mass

        self.length      = self.bedplate_length                              # nacelle length [m] based on bedplate length
        self.width       = self.bedplate_width                        # nacelle width [m] based on bedplate width
        self.height      = (2.0 / 3.0) * self.length                         # nacelle height [m] calculated based on cladding area

#--------------------------------------------
class RNASystemAdder_drive(Component):
    ''' RNASystem class
          This analysis is only to be used in placing the transformer of the drivetrain.
          The Rotor-Nacelle-Assembly class is used to represent the RNA of the turbine without the transformer and bedplate (to resolve circular dependency issues).
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component. 
    '''
    #inputs
    yawMass = Float(iotype='in', units='kg', desc='mass of yaw system')
    lss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    main_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    second_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    gearbox_mass = Float(iotype = 'in', units='kg', desc='component mass')
    hss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    generator_mass = Float(iotype = 'in', units='kg', desc='component mass')
    lss_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    main_bearing_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    second_bearing_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    gearbox_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    hss_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    generator_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    overhang = Float(iotype = 'in', units='m', desc='nacelle overhang')
    rotor_mass = Float(iotype = 'in', units='kg', desc='component mass')
    machine_rating = Float(iotype = 'in', units = 'kW', desc = 'machine rating ')

    #returns
    RNA_mass = Float(iotype = 'out', units='kg', desc='mass of total RNA')
    RNA_cm = Float(iotype='out', units='m', desc='RNA CM along x-axis')

    def __init__(self):
        ''' Initialize RNA Adder component
        '''

        super(RNASystemAdder_drive , self).__init__()

        #controls what happens if derivatives are missing
        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        if self.rotor_mass:
            rotor_mass = self.rotor_mass
        else:
            rotor_mass = get_rotor_mass(self.machine_rating)

        masses = np.array([rotor_mass, self.yawMass, self.lss_mass, self.main_bearing_mass,self.second_bearing_mass,self.gearbox_mass,self.hss_mass,self.generator_mass])
        cms = np.array([(-self.overhang), 0.0, self.lss_cm[0], self.main_bearing_cm[0], self.second_bearing_cm[0], self.gearbox_cm[0], self.hss_cm[0], self.generator_cm[0]])

        self.RNA_mass = np.sum(masses)
        self.RNA_cm = np.sum(masses*cms)/np.sum(masses)
        # print self.RNA_mass
        # print self.RNA_cm
        

#--------------------------------------------
class NacelleSystemAdder_drive(Component): #added to drive to include transformer
    ''' NacelleSystem class
          The Nacelle class is used to represent the overall nacelle of a wind turbine.
          It contains the general properties for a wind turbine component as well as additional design load and dimentional attributes as listed below.
          It contains an update method to determine the mass, mass properties, and dimensions of the component.
    '''
    # variables
    above_yaw_mass = Float(iotype='in', units='kg', desc='mass above yaw system')
    yawMass = Float(iotype='in', units='kg', desc='mass of yaw system')
    lss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    main_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    second_bearing_mass = Float(iotype = 'in', units='kg', desc='component mass')
    gearbox_mass = Float(iotype = 'in', units='kg', desc='component mass')
    hss_mass = Float(iotype = 'in', units='kg', desc='component mass')
    generator_mass = Float(iotype = 'in', units='kg', desc='component mass')
    bedplate_mass = Float(iotype = 'in', units='kg', desc='component mass')
    mainframe_mass = Float(iotype = 'in', units='kg', desc='component mass')
    lss_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    main_bearing_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    second_bearing_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    gearbox_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    hss_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    generator_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    bedplate_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    lss_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    main_bearing_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    second_bearing_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    gearbox_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    hss_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    generator_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    bedplate_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')
    transformer_mass = Float(iotype = 'in', units='kg', desc='component mass')
    transformer_cm = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component CM')
    transformer_I = Array(np.array([0.0,0.0,0.0]),iotype = 'in', units='kg', desc='component I')

    # returns
    nacelle_mass = Float(0.0, iotype='out', units='kg', desc='overall component mass')
    nacelle_cm = Array(np.array([0.0, 0.0, 0.0]), units='m', iotype='out', desc='center of mass of the component in [x,y,z] for an arbitrary coordinate system')
    nacelle_I = Array(np.array([0.0, 0.0, 0.0]), units='kg*m**2', iotype='out', desc=' moments of Inertia for the component [Ixx, Iyy, Izz] around its center of mass')

    def __init__(self):
        ''' Initialize above yaw mass adder component
        '''

        super(NacelleSystemAdder_drive , self).__init__()

        #controls what happens if derivatives are missing
        self.missing_deriv_policy = 'assume_zero'

    def execute(self):

        # aggregation of nacelle mass
        self.nacelle_mass = (self.above_yaw_mass + self.yawMass)

        # calculation of mass center and moments of inertia
        cm = np.array([0.0,0.0,0.0])
        for i in (range(0,3)):
            # calculate center of mass (use mainframe_mass in place of bedplate_mass - assume lumped around bedplate_cm)
            cm[i] = (self.lss_mass * self.lss_cm[i] + self.transformer_cm[i] * self.transformer_mass + \
                    self.main_bearing_mass * self.main_bearing_cm[i] + self.second_bearing_mass * self.second_bearing_cm[i] + \
                    self.gearbox_mass * self.gearbox_cm[i] + self.hss_mass * self.hss_cm[i] + \
                    self.generator_mass * self.generator_cm[i] + self.mainframe_mass * self.bedplate_cm[i] ) / \
                    (self.lss_mass + self.main_bearing_mass + self.second_bearing_mass + \
                    self.gearbox_mass + self.hss_mass + self.generator_mass + self.mainframe_mass)
        self.nacelle_cm = cm

        I = np.zeros(6)
        for i in (range(0,3)):                        # calculating MOI, at nacelle center of gravity with origin at tower top center / yaw mass center, ignoring masses of non-drivetrain components / auxiliary systems
            # calculate moments around CM
            # sum moments around each components CM (adjust for mass of mainframe) # TODO: add yaw MMI
            I[i]  =  self.lss_I[i] + self.main_bearing_I[i] + self.second_bearing_I[i] + self.gearbox_I[i] + self.transformer_I[i] +\
                          self.hss_I[i] + self.generator_I[i] + self.bedplate_I[i] * (self.mainframe_mass / self.bedplate_mass)
            # translate to nacelle CM using parallel axis theorem (use mass of mainframe en lieu of bedplate to account for auxiliary equipment)
            for j in (range(0,3)):
                if i != j:
                    I[i] +=  self.lss_mass * (self.lss_cm[j] - cm[j]) ** 2 + \
                                  self.main_bearing_mass * (self.main_bearing_cm[j] - cm[j]) ** 2 + \
                                  self.second_bearing_mass * (self.second_bearing_cm[j] - cm[j]) ** 2 + \
                                  self.gearbox_mass * (self.gearbox_cm[j] - cm[j]) ** 2 + \
                                  self.transformer_mass * (self.transformer_cm[j] - cm[j]) ** 2 + \
                                  self.hss_mass * (self.hss_cm[j] - cm[j]) ** 2 + \
                                  self.generator_mass * (self.generator_cm[j] - cm[j]) ** 2 + \
                                  self.mainframe_mass * (self.bedplate_cm[j] - cm[j]) ** 2
        self.nacelle_I = I


if __name__ == '__main__':
     pass
