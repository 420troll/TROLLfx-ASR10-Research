// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 TROLLfx contributors
#include "mpc_plugin.h"
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>
namespace {
const char* const names[]={
"01 HALL REVERB [UNAVAILABLE]","02 44KHZ REVERB [IDENTITY CONFLICT]","03 ROOM REVERB [IDENTITY AMBIGUOUS]","04 DUAL DELAYS [UNAVAILABLE]","05 44KHZ DELAYS [UNAVAILABLE]","06 CHORUS+REVRB [UNAVAILABLE]","07 PHASER+REVRB [UNAVAILABLE]","08 FLANGER+REV [UNAVAILABLE]","09 ROT.SPKR+REV [UNAVAILABLE]","10 CHOR+REV+DDL [UNAVAILABLE]","11 CMP+DIST+REV [UNAVAILABLE]","12 DIST+CHO+REV [UNAVAILABLE]","13 WAH+DIST+REV [UNAVAILABLE]","14 SMALL ROOM [UNAVAILABLE]","15 LARGE ROOM [UNAVAILABLE]","16 HALL REVERB2 [UNAVAILABLE]","17 SMALL PLATE [UNAVAILABLE]","18 LARGE PLATE [UNAVAILABLE]","19 REVRSE REVRB [UNAVAILABLE]","20 REVRSE REVB2 [UNAVAILABLE]","21 GATED REVERB [UNAVAILABLE]","22 NLIN REVRB 1 [UNAVAILABLE]","23 NLIN REVRB 2 [UNAVAILABLE]","24 NLIN REVRB 3 [UNAVAILABLE]","25 MULTITAP DDL [UNAVAILABLE]","26 EQ+DELAY LFO [UNAVAILABLE]","27 VCF+DISTORT [UNAVAILABLE]","28 GUITAR AMP1 [UNAVAILABLE]","29 GUITAR AMP2 [UNAVAILABLE]","30 GUITAR AMP3 [UNAVAILABLE]","31 SPKR CABINET [UNAVAILABLE]","32 TUNABLE SPKR [UNAVAILABLE]","33 EQ+CHOR+DDL [UNAVAILABLE]","34 EQ+VIBR+DDL [UNAVAILABLE]","35 EQ+FLNGR+DDL [UNAVAILABLE]","36 EQ+TREM+DDL [UNAVAILABLE]","37 PHASER+DDL [UNAVAILABLE]","38 8-VOICE CHOR [UNAVAILABLE]","39 PITCH SHIFT [UNAVAILABLE]","40 PITCH+DDL [UNAVAILABLE]","41 FAST PITCHSH [UNAVAILABLE]","42 EQ+CMPRESSOR [UNAVAILABLE]","43 EXPANDER [UNAVAILABLE]","44 KEYED EXPNDR [UNAVAILABLE]","45 INVRS EXPNDR [UNAVAILABLE]","46 DE-ESSER [UNAVAILABLE]","47 DUCKER [UNAVAILABLE]","48 RUMBLE FILTR [UNAVAILABLE]","49 PARAM EQ [UNAVAILABLE]","50 VAN DER POL [UNAVAILABLE]"};

}
class ASR10FXCollection final:public mpc::Plugin{enum{Fx=0,Wet,In,Out,Bypass,Status,BUS1,BUS2};static mpc::PluginInfo makeInfo(){mpc::PluginInfo i;i.name="ASR10 FX Collection";i.vendor="TROLLfx";i.uniqueId=MPC_FOURCC('T','f','x','F');i.version=1000;i.isInstrument=false;i.numInputs=2;i.numOutputs=2;return i;}public:
ASR10FXCollection():mpc::Plugin(makeInfo()){using namespace mpc;std::vector<std::string> es;for(auto n:names)es.emplace_back(n);addParam(choiceParam("effect_slot","FX Slot",es,0));addParam(floatParam("host_wet","Wet / Dry",0,100,100,"%",0));addParam(floatParam("host_input_gain","Input Gain",-24,24,0,"dB",1));addParam(floatParam("host_output_gain","Output Gain",-24,24,0,"dB",1));addParam(boolParam("host_bypass","Host Bypass",false));addParam(choiceParam("load_status","Load Status",{"Package required","Unavailable","Ready","Load failed"},0));addParam(choiceParam("reverb_bus1","Reverb BUS1",{"HALL 28","HALL 29","ROM02 25","ROM02 26"},0));addParam(choiceParam("reverb_bus2","Reverb BUS2",{"HALL 28","HALL 29","ROM02 25","ROM02 26"},0));}
void prepare(double,int)override{} void reset()override{}
void process(mpc::ProcessContext& c)override{int s=std::clamp(getInt(Fx),0,49);set(Status,float(s==1?3:(s==2?3:1)));for(int i=0;i<c.numFrames;++i)for(int ch=0;ch<2;++ch)c.outputs[ch][i]=0.f;}
};
MPC_PLUGIN_ENTRY(ASR10FXCollection)
