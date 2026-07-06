(* ============================================================
   08_GVL_WeightPolicy_generated.st — 生成文件,勿手改!
   由 sim/adaptive_weights.py 生成:场景→权重 策略表(A1 自适应机制)
   场景判档(PLC 在线可算):iDensity 0/1/2=占用率<55%/<85%/其余;
   iDist 0/1/2=均匀/高频偏态/重货(按库存重量均值与频次变异系数判,见 FC_ClassifyScene);
   xBatch FALSE=在线逐件 TRUE=批量重排。
   ============================================================ *)
VAR_GLOBAL CONSTANT
    // aPolicyDelta/aPolicyBG[iDensity, iDist, xBatch(0/1)]
    aPolicyDelta : ARRAY[0..2, 0..2, 0..1] OF REAL := [
        0.2, 0.15, 0.1, 0.05, 0.1, 0.1, 0.2, 0.2, 0.15, 0.05, 0.2, 0.1, 0.2, 0.2, 0.2, 0.05, 0.2, 0.15];
    aPolicyBG : ARRAY[0..2, 0..2, 0..1] OF REAL := [
        0.6, 0.6, 1.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6];
END_VAR

(* 用法(PRG_Main 分配启动前调用):
   GVL_Param.rDelta := aPolicyDelta[iDensity, iDist, SEL(xBatch, 0, 1)];
   bg := aPolicyBG[iDensity, iDist, SEL(xBatch, 0, 1)];
   GVL_Param.rBeta := bg / 2.0;  GVL_Param.rGamma := bg / 2.0;  *)
