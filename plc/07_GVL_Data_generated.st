(* ============================================================
   07_GVL_Data_generated.st — 生成文件,勿手改!
   由 sim/export_st_vectors.py 生成(seed=2026,N_DEMO=20,
   评分权重 α=1.0 β=0.6 γ=0.4 δ=0.15 = canonical E 默认)
   导入:TYPE 段建 DUT;GVL_Data 段建 GVL;FC_LoadDemoGoods 建 POU(函数)
   ============================================================ *)

(* ---------- DUT:ST_TestVec ---------- *)
TYPE ST_TestVec :
STRUCT
    W        : REAL;   // 货物重量
    F        : REAL;   // 货物频次
    X        : INT;    // 候选仓位列
    Y        : INT;    // 候选仓位层
    WMax     : REAL;   // 归一分母
    FMax     : REAL;
    ExpScore : REAL;   // Python 期望评分(双精度算出,容差1e-3比对)
    ExpTime  : REAL;   // Python 期望切比雪夫时间
END_STRUCT
END_TYPE

(* ---------- GVL:GVL_Data ---------- *)
VAR_GLOBAL CONSTANT
    N_DEMO    : INT := 20;
    N_TESTVEC : INT := 10;
END_VAR
VAR_GLOBAL
    aTestVec : ARRAY[1..10] OF ST_TestVec := [
        (W := 13.9, F := 1.83, X := 1, Y := 0, WMax := 80.0, FMax := 9.82, ExpScore := 0.122893, ExpTime := 0.500000),
        (W := 69.5, F := 1.1, X := 5, Y := 2, WMax := 80.0, FMax := 9.82, ExpScore := 0.222415, ExpTime := 4.000000),
        (W := 50.1, F := 2.02, X := 10, Y := 5, WMax := 80.0, FMax := 9.82, ExpScore := 0.306726, ExpTime := 10.000000),
        (W := 46.1, F := 3.1, X := 19, Y := 19, WMax := 80.0, FMax := 9.82, ExpScore := 0.891932, ExpTime := 38.000000),
        (W := 61.3, F := 2.14, X := 0, Y := 1, WMax := 80.0, FMax := 9.82, ExpScore := 0.162936, ExpTime := 2.000000),
        (W := 51.1, F := 1.11, X := 3, Y := 3, WMax := 80.0, FMax := 9.82, ExpScore := 0.230741, ExpTime := 6.000000),
        (W := 38.7, F := 4.28, X := 7, Y := 10, WMax := 80.0, FMax := 9.82, ExpScore := 0.524082, ExpTime := 20.000000),
        (W := 56.0, F := 1.23, X := 15, Y := 1, WMax := 80.0, FMax := 9.82, ExpScore := 0.166878, ExpTime := 7.500000),
        (W := 78.5, F := 9.82, X := 2, Y := 18, WMax := 80.0, FMax := 9.82, ExpScore := 1.876974, ExpTime := 36.000000),
        (W := 80.0, F := 1.86, X := 12, Y := 7, WMax := 80.0, FMax := 9.82, ExpScore := 0.514996, ExpTime := 14.000000)
    ];
END_VAR

(* ---------- FC_LoadDemoGoods:载入演示批次(与 Python 仿真同源同 seed) ---------- *)
FUNCTION FC_LoadDemoGoods : BOOL
VAR
    n : INT;
END_VAR
n := GVL_WH.iGoodsCount;
n := n + 1;  GVL_WH.aGoods[n].Id := 1;  GVL_WH.aGoods[n].Name := 'G001';
GVL_WH.aGoods[n].Weight := 13.9;  GVL_WH.aGoods[n].Freq := 1.83;  GVL_WH.aGoods[n].Volume := 0.51;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 2;  GVL_WH.aGoods[n].Name := 'G002';
GVL_WH.aGoods[n].Weight := 69.5;  GVL_WH.aGoods[n].Freq := 1.1;  GVL_WH.aGoods[n].Volume := 0.28;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 3;  GVL_WH.aGoods[n].Name := 'G003';
GVL_WH.aGoods[n].Weight := 50.1;  GVL_WH.aGoods[n].Freq := 2.02;  GVL_WH.aGoods[n].Volume := 0.73;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 4;  GVL_WH.aGoods[n].Name := 'G004';
GVL_WH.aGoods[n].Weight := 46.1;  GVL_WH.aGoods[n].Freq := 3.1;  GVL_WH.aGoods[n].Volume := 0.71;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 5;  GVL_WH.aGoods[n].Name := 'G005';
GVL_WH.aGoods[n].Weight := 61.3;  GVL_WH.aGoods[n].Freq := 2.14;  GVL_WH.aGoods[n].Volume := 0.29;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 6;  GVL_WH.aGoods[n].Name := 'G006';
GVL_WH.aGoods[n].Weight := 51.1;  GVL_WH.aGoods[n].Freq := 1.11;  GVL_WH.aGoods[n].Volume := 0.75;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 7;  GVL_WH.aGoods[n].Name := 'G007';
GVL_WH.aGoods[n].Weight := 38.7;  GVL_WH.aGoods[n].Freq := 4.28;  GVL_WH.aGoods[n].Volume := 0.65;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 8;  GVL_WH.aGoods[n].Name := 'G008';
GVL_WH.aGoods[n].Weight := 56.0;  GVL_WH.aGoods[n].Freq := 1.23;  GVL_WH.aGoods[n].Volume := 0.3;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 9;  GVL_WH.aGoods[n].Name := 'G009';
GVL_WH.aGoods[n].Weight := 78.5;  GVL_WH.aGoods[n].Freq := 9.82;  GVL_WH.aGoods[n].Volume := 0.74;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 10;  GVL_WH.aGoods[n].Name := 'G010';
GVL_WH.aGoods[n].Weight := 80.0;  GVL_WH.aGoods[n].Freq := 1.86;  GVL_WH.aGoods[n].Volume := 0.16;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 11;  GVL_WH.aGoods[n].Name := 'G011';
GVL_WH.aGoods[n].Weight := 30.5;  GVL_WH.aGoods[n].Freq := 2.02;  GVL_WH.aGoods[n].Volume := 0.33;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 12;  GVL_WH.aGoods[n].Name := 'G012';
GVL_WH.aGoods[n].Weight := 39.3;  GVL_WH.aGoods[n].Freq := 6.07;  GVL_WH.aGoods[n].Volume := 0.66;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 13;  GVL_WH.aGoods[n].Name := 'G013';
GVL_WH.aGoods[n].Weight := 48.3;  GVL_WH.aGoods[n].Freq := 1.02;  GVL_WH.aGoods[n].Volume := 0.67;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 14;  GVL_WH.aGoods[n].Name := 'G014';
GVL_WH.aGoods[n].Weight := 32.3;  GVL_WH.aGoods[n].Freq := 1.6;  GVL_WH.aGoods[n].Volume := 0.42;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 15;  GVL_WH.aGoods[n].Name := 'G015';
GVL_WH.aGoods[n].Weight := 48.9;  GVL_WH.aGoods[n].Freq := 1.81;  GVL_WH.aGoods[n].Volume := 0.19;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 16;  GVL_WH.aGoods[n].Name := 'G016';
GVL_WH.aGoods[n].Weight := 43.0;  GVL_WH.aGoods[n].Freq := 3.31;  GVL_WH.aGoods[n].Volume := 0.58;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 17;  GVL_WH.aGoods[n].Name := 'G017';
GVL_WH.aGoods[n].Weight := 41.8;  GVL_WH.aGoods[n].Freq := 8.53;  GVL_WH.aGoods[n].Volume := 0.31;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 18;  GVL_WH.aGoods[n].Name := 'G018';
GVL_WH.aGoods[n].Weight := 36.5;  GVL_WH.aGoods[n].Freq := 9.46;  GVL_WH.aGoods[n].Volume := 0.48;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 19;  GVL_WH.aGoods[n].Name := 'G019';
GVL_WH.aGoods[n].Weight := 43.8;  GVL_WH.aGoods[n].Freq := 1.02;  GVL_WH.aGoods[n].Volume := 0.28;  GVL_WH.aGoods[n].Assigned := FALSE;
n := n + 1;  GVL_WH.aGoods[n].Id := 20;  GVL_WH.aGoods[n].Name := 'G020';
GVL_WH.aGoods[n].Weight := 14.7;  GVL_WH.aGoods[n].Freq := 1.04;  GVL_WH.aGoods[n].Volume := 0.66;  GVL_WH.aGoods[n].Assigned := FALSE;
GVL_WH.iGoodsCount := n;
FC_LoadDemoGoods := TRUE;
END_FUNCTION
