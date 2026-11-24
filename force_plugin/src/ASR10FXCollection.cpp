// SPDX-License-Identifier: GPL-3.0-only
// Copyright (C) 2026 TROLLfx contributors
#include "mpc_plugin.h"
#include "ES5510DSPBackend.h"
#include "ES5510FactoryPackageProvider.h"
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

namespace {
const char* const names[]={
 "01 HALL REVERB","02 44KHZ REVERB","03 ROOM REVERB","04 DUAL DELAYS","05 44KHZ DELAYS",
 "06 CHORUS+REVRB","07 PHASER+REVRB","08 FLANGER+REV","09 ROT.SPKR+REV","10 CHOR+REV+DDL",
 "11 CMP+DIST+REV","12 DIST+CHO+REV","13 WAH+DIST+REV","14 SMALL ROOM","15 LARGE ROOM",
 "16 HALL REVERB2","17 SMALL PLATE","18 LARGE PLATE","19 REVRSE REVRB","20 REVRSE REVB2",
 "21 GATED REVERB","22 NLIN REVRB 1","23 NLIN REVRB 2","24 NLIN REVRB 3","25 MULTITAP DDL",
 "26 EQ+DELAY LFO","27 VCF+DISTORT","28 GUITAR AMP1","29 GUITAR AMP2","30 GUITAR AMP3",
 "31 SPKR CABINET","32 TUNABLE SPKR","33 EQ+CHOR+DDL","34 EQ+VIBR+DDL","35 EQ+FLNGR+DDL",
 "36 EQ+TREM+DDL","37 PHASER+DDL","38 8-VOICE CHOR","39 PITCH SHIFT","40 PITCH+DDL",
 "41 FAST PITCHSH","42 EQ+CMPRESSOR","43 EXPANDER","44 KEYED EXPNDR","45 INVRS EXPNDR",
 "46 DE-ESSER","47 DUCKER","48 RUMBLE FILTR","49 PARAM EQ","50 VAN DER POL"};
const IValidatedFactoryPackageProvider* resolve_provider(){
 auto*p=TROLLfx_GetValidatedFactoryPackageProvider();
 return p?p:TROLLfx_GetProductionFactoryPackageProvider();
}
std::vector<std::string> effect_names(){
 std::vector<std::string> out;out.reserve(50);auto*p=resolve_provider();
 for(unsigned i=0;i<50;++i){std::string s=names[i];s+=p&&p->package_for_slot(static_cast<std::uint8_t>(i+1))?" [READY]":" [UNAVAILABLE]";out.push_back(std::move(s));}
 return out;
}
}

class ASR10FXCollection final:public mpc::Plugin {
 enum{Fx=0,Wet,In,Out,Bypass,Status,BUS1,BUS2};
 static mpc::PluginInfo makeInfo(){mpc::PluginInfo i;i.name="ASR10 FX Collection";i.vendor="TROLLfx";i.uniqueId=MPC_FOURCC('T','f','x','F');i.version=1000;i.isInstrument=false;i.numInputs=2;i.numOutputs=2;return i;}
public:
 ASR10FXCollection():mpc::Plugin(makeInfo()),backend_(resolve_provider()){
  using namespace mpc;
  addParam(choiceParam("effect_slot","FX Slot",effect_names(),0));
  addParam(floatParam("host_wet","Wet / Dry",0,100,100,"%",0));
  addParam(floatParam("host_input_gain","Input Gain",-24,24,0,"dB",1));
  addParam(floatParam("host_output_gain","Output Gain",-24,24,0,"dB",1));
  addParam(boolParam("host_bypass","Host Bypass",false));
  addParam(choiceParam("load_status","Load Status",{"See FX Slot status"},0));
  addParam(choiceParam("reverb_bus1","Reverb BUS1",{"HALL 28","HALL 29","ROM02 25","ROM02 26"},0));
  addParam(choiceParam("reverb_bus2","Reverb BUS2",{"HALL 28","HALL 29","ROM02 25","ROM02 26"},0));
 }
 void prepare(double rate,int)override{
  host_rate_=rate;int selected=std::clamp(getInt(Fx),0,49);
  backend_.prepare(static_cast<std::uint8_t>(selected+1),rate);
 }
 void reset()override{}
 void process(mpc::ProcessContext& c)override{
  int selected=std::clamp(getInt(Fx),0,49);auto slot=static_cast<std::uint8_t>(selected+1);
  backend_.request_effect(slot);backend_.set_mix(get(Wet)/100.f,get(In),get(Out),getInt(Bypass)!=0);
  const float* in[2]={c.inputs?c.inputs[0]:nullptr,c.inputs?c.inputs[1]:nullptr};
  float* out[2]={c.outputs?c.outputs[0]:nullptr,c.outputs?c.outputs[1]:nullptr};
  backend_.process(in,out,static_cast<std::size_t>(std::max(0,c.numFrames)));
 }
 bool formatValue(int index,float,std::string&out)override{
  if(index!=Status)return false;
  int selected=std::clamp(getInt(Fx),0,49);
  auto slot=static_cast<std::uint8_t>(selected+1);
  auto s=backend_.status();
  if(s==ES5510BackendStatus::NoProvider)out="MISSING";
  else if(s==ES5510BackendStatus::Unavailable)out="UNAVAIL";
  else if(s==ES5510BackendStatus::Failed)out="LOAD ERR";
  else if(s==ES5510BackendStatus::Loading||backend_.active_slot()!=slot)out="LOADING";
  else out="READY";
  return true;
 }
private:
 ES5510DSPBackend backend_;double host_rate_=48000.0;
};

#ifndef TROLLFX_FORCE_PLUGIN_TEST
MPC_PLUGIN_ENTRY(ASR10FXCollection)
#endif
