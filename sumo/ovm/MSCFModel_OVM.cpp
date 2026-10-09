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
/// @file    MSCFModel_OVM.cpp
/// @author  Lao Zhongjie
/// @date    Sat, 10 Oct 2026
///
// The Optimal Velocity Model (Bando et al. 1995)
/****************************************************************************/
#include <config.h>

#include <cmath>
#include <limits>
#include <microsim/MSVehicle.h>
#include <microsim/MSVehicleType.h>
#include <microsim/MSLane.h>
#include <microsim/MSGlobals.h>
#include <utils/common/ToString.h>
#include "MSCFModel_OVM.h"

// ===========================================================================
// method definitions
// ===========================================================================
MSCFModel_OVM::MSCFModel_OVM(const MSVehicleType* vtype) :
    MSCFModel(vtype),
    // defaults close to the fit to highway data in Bando et al. (1995), with maxSpeed = 32 m/s
    myAlpha(vtype->getParameter().getCFParam(SUMO_ATTR_CF_OVM_ALPHA, 2.0)),
    mySc(vtype->getParameter().getCFParam(SUMO_ATTR_CF_OVM_SC, 18.0)),
    myD(vtype->getParameter().getCFParam(SUMO_ATTR_CF_OVM_D, 11.6)),
    myTanhScD(tanh(mySc / myD)),
    // 1 - tanh(x) < 1e-16 for x > 19
    myRange(mySc + 19. * myD) {
    if (myAlpha <= 0. || myD <= 0.) {
        throw ProcessError(TLF("OVM parameters alpha and d of vType '%' must be positive.", vtype->getID()));
    }
    // explicit relaxation overshoots V when alpha * dt > 1 and diverges when alpha * dt > 2
    if (myAlpha * TS > 1.) {
        WRITE_WARNINGF(TL("OVM in vType '%': alpha * step-length = % > 1, so each step overshoots the optimal speed."), vtype->getID(), toString(myAlpha * TS));
    }
}


MSCFModel_OVM::~MSCFModel_OVM() {}


double
MSCFModel_OVM::optimalSpeed(double gap, double vMax) const {
    return vMax * (tanh((gap - mySc) / myD) + myTanhScD) / (1. + myTanhScD);
}


double
MSCFModel_OVM::relax(double speed, double target) const {
    return MAX2(0., speed + ACCEL2SPEED(myAlpha * (target - speed)));
}


double
MSCFModel_OVM::laneMaxSpeed(const MSVehicle* const veh) const {
    return veh->getLane() != nullptr ? veh->getLane()->getVehicleMaxSpeed(veh) : veh->getMaxSpeed();
}


double
MSCFModel_OVM::freeSpeed(const MSVehicle* const veh, double speed, double seen, double maxSpeed, const bool onInsertion, const CalcReason usage) const {
    // never exceed a lower speed limit ahead
    const double vLimit = MSCFModel::freeSpeed(veh, speed, seen, maxSpeed, onInsertion, usage);
    if (onInsertion || veh->getLane() == nullptr) {
        return vLimit;
    }
    double target = maxSpeed;
    const std::pair<const MSVehicle* const, double> leader = veh->getLeader(myRange, false);
    if (leader.first != nullptr) {
        target = optimalSpeed(leader.second, maxSpeed);
    }
    return MIN2(vLimit, relax(speed, target));
}


double
MSCFModel_OVM::followSpeed(const MSVehicle* const veh, double speed, double gap2pred,
                           double /*predSpeed*/, double /*predMaxDecel*/, const MSVehicle* const /*pred*/, const CalcReason /*usage*/) const {
    return relax(speed, optimalSpeed(gap2pred, laneMaxSpeed(veh)));
}


double
MSCFModel_OVM::insertionFollowSpeed(const MSVehicle* const veh, double /*speed*/, double gap2pred, double /*predSpeed*/, double /*predMaxDecel*/, const MSVehicle* const /*pred*/) const {
    return MAX2(0., optimalSpeed(gap2pred, laneMaxSpeed(veh)));
}


double
MSCFModel_OVM::stopSpeed(const MSVehicle* const veh, const double speed, double gap, double /*decel*/, const CalcReason /*usage*/) const {
    if (gap < NUMERICAL_EPS) {
        return 0.;
    }
    // a stop line acts like a standing leader; V(gap) > 0 for gap > 0, so the line is always reached
    return MIN2(relax(speed, optimalSpeed(gap, laneMaxSpeed(veh))), DIST2SPEED(gap));
}


double
MSCFModel_OVM::maxNextSpeed(double /*speed*/, const MSVehicle* const /*veh*/) const {
    return myType->getMaxSpeed();
}


double
MSCFModel_OVM::minNextSpeedEmergency(double /*speed*/, const MSVehicle* const /*veh*/) const {
    if (MSGlobals::gSemiImplicitEulerUpdate) {
        return 0.;
    }
    return -std::numeric_limits<double>::max();
}


MSCFModel*
MSCFModel_OVM::duplicate(const MSVehicleType* vtype) const {
    return new MSCFModel_OVM(vtype);
}


/****************************************************************************/
