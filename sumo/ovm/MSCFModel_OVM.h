/****************************************************************************/
// Eclipse SUMO, Simulation of Urban MObility; see https://eclipse.dev/sumo
// Copyright (C) 2026-2026 German Aerospace Center (DLR) and others.
// This program and the accompanying materials are made available under the
// terms of the Eclipse Public License 2.0 which is available at
// https://www.eclipse.org/legal/epl-2.0/
// This Source Code may also be made available under the following Secondary
// Licenses when the conditions for such availability set forth in the Eclipse
// Public License 2.0 are satisfied: GNU General Public License, version 2
// or later which is available at
// https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
// SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later
/****************************************************************************/
/// @file    MSCFModel_OVM.h
/// @author  Lao Zhongjie
/// @date    Sat, 10 Oct 2026
///
// The Optimal Velocity Model (Bando et al. 1995)
/****************************************************************************/
#pragma once
#include <config.h>

#include "MSCFModel.h"
#include <utils/xml/SUMOXMLDefinitions.h>


// ===========================================================================
// class definitions
// ===========================================================================
/** @class MSCFModel_OVM
 * @brief The Optimal Velocity Model (Bando et al. 1995)
 *
 * Each vehicle relaxes towards the optimal speed of its gap s:
 *
 *   dv/dt = alpha * (V(s) - v)
 *   V(s)  = vmax * (tanh((s - sc) / d) + tanh(sc / d)) / (1 + tanh(sc / d))
 *
 * integrated with SUMO's position update (semi-implicit Euler by default):
 * v(t + dt) = v + dt * alpha * (V(s) - v).
 *
 * - s is SUMO's gap: the bumper-to-bumper distance minus minGap. V(0) = 0, so
 *   a jam stops at minGap instead of overlapping. With minGap = 0 and vehicle
 *   length l, the headway is h = s + l.
 * - vmax is the vehicle's maximum speed on its lane, i.e. the smaller of
 *   maxSpeed and the lane speed limit times the speed factor.
 * - alpha (1/s), sc (m) and d (m) are the vType attributes alpha, sc and d.
 *   sc is the gap where V is steepest and d sets the width of the transition.
 *
 * Like the original model, OVM has no acceleration bounds: accel and decel do
 * not limit its speed changes (they still enter SUMO's look-ahead and stop
 * decisions). The speed is only clipped at 0, and when approaching a stop
 * line it may not overshoot the line.
 *
 * @see MSCFModel
 * @see https://doi.org/10.1103/PhysRevE.51.1035
 */
class MSCFModel_OVM : public MSCFModel {
public:
    /** @brief Constructor
     *  @param[in] vtype the type for which this model is built and also the parameter object to configure this model
     */
    MSCFModel_OVM(const MSVehicleType* vtype);


    /// @brief Destructor
    ~MSCFModel_OVM();


    /// @name Implementations of the MSCFModel interface
    /// @{

    /** @brief Computes the vehicle's speed on a free road (no leader within SUMO's look-ahead)
     *
     * SUMO looks for leaders only within the vehicle's brake gap, which can be
     * shorter than the range of V(s). The leader is therefore searched again up
     * to the distance where V(s) equals vmax to double precision.
     * @param[in] veh The vehicle (EGO)
     * @param[in] speed The vehicle's speed
     * @param[in] seen The look ahead distance
     * @param[in] maxSpeed The maximum allowed speed
     * @return EGO's next speed
     */
    double freeSpeed(const MSVehicle* const veh, double speed, double seen,
                     double maxSpeed, const bool onInsertion = false, const CalcReason usage = CalcReason::CURRENT) const;


    /** @brief Computes the vehicle's next speed behind a leader
     * @param[in] veh The vehicle (EGO)
     * @param[in] speed The vehicle's speed
     * @param[in] gap2pred The (net) distance to the LEADER
     * @param[in] predSpeed The speed of LEADER (not used by OVM)
     * @return EGO's next speed
     */
    double followSpeed(const MSVehicle* const veh, double speed, double gap2pred,
                       double predSpeed, double predMaxDecel, const MSVehicle* const pred = 0, const CalcReason usage = CalcReason::CURRENT) const;


    /** @brief Computes the speed allowed at insertion behind a leader
     *
     * Returns the optimal speed of the gap, so that departSpeed="max" starts
     * the vehicle in uniform flow.
     * @param[in] veh The vehicle (EGO)
     * @param[in] speed The vehicle's speed
     * @param[in] gap2pred The (net) distance to the LEADER
     * @param[in] predSpeed The speed of LEADER
     * @return EGO's allowed insertion speed
     */
    double insertionFollowSpeed(const MSVehicle* const veh, double speed, double gap2pred, double predSpeed, double predMaxDecel, const MSVehicle* const pred = 0) const;


    /** @brief Computes the vehicle's next speed when approaching a non-moving obstacle
     * @param[in] veh The vehicle (EGO)
     * @param[in] speed The vehicle's speed
     * @param[in] gap The (net) distance to the obstacle
     * @param[in] decel used only to reach a stop from standstill
     * @return EGO's next speed
     */
    double stopSpeed(const MSVehicle* const veh, const double speed, double gap, double decel, const CalcReason usage = CalcReason::CURRENT) const;


    /// @brief OVM does not bound acceleration: the next speed is limited only by maxSpeed
    double maxNextSpeed(double speed, const MSVehicle* const veh) const;


    /// @brief OVM does not bound deceleration: the vehicle may stop within one step
    double minNextSpeedEmergency(double speed, const MSVehicle* const veh = 0) const;


    /** @brief Returns the model's name
     * @return The model's name
     */
    int getModelID() const {
        return SUMO_TAG_CF_OVM;
    }
    /// @}


    /** @brief Duplicates the car-following model
     * @param[in] vtype The vehicle type this model belongs to (1:1)
     * @return A duplicate of this car-following model
     */
    MSCFModel* duplicate(const MSVehicleType* vtype) const;


    /** @brief The optimal speed V(s)
     * @param[in] gap the (net) gap s, in m
     * @param[in] vMax the speed approached for large gaps
     * @return V(s); negative for negative gaps
     */
    double optimalSpeed(double gap, double vMax) const;

protected:
    /// @brief one step of dv/dt = alpha * (target - v), clipped at 0
    double relax(double speed, double target) const;

    /// @brief the vehicle's maximum speed on its lane (vmax)
    double laneMaxSpeed(const MSVehicle* const veh) const;

protected:
    /// @brief The sensitivity alpha, in 1/s
    double myAlpha;

    /// @brief The gap where V is steepest, in m
    double mySc;

    /// @brief The width of the transition of V, in m
    double myD;

    /// @brief tanh(sc / d), the offset that makes V(0) = 0
    double myTanhScD;

    /// @brief The gap beyond which V(s) equals vmax to double precision, in m
    double myRange;
};
