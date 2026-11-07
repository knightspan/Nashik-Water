#pragma once
#include <cstdarg>
namespace Eloquent {
    namespace ML {
        namespace Port {
            class WaterStateTree {
                public:
                    /**
                    * Predict class for features vector
                    */
                    int predict(float *x) {
                        if (x[1] <= 1.204908013343811) {
                            if (x[2] <= 1.473012089729309) {
                                if (x[3] <= -19.14577579498291) {
                                    if (x[5] <= 0.005982300732284784) {
                                        if (x[3] <= -35.79028511047363) {
                                            return 2;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }

                                    else {
                                        if (x[0] <= 0.025420752353966236) {
                                            return 2;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }

                                else {
                                    if (x[4] <= -1.0134131908416748) {
                                        if (x[2] <= 1.0109307169914246) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        if (x[4] <= 3.706585168838501) {
                                            return 0;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }
                            }

                            else {
                                if (x[3] <= -12.745471477508545) {
                                    if (x[5] <= 0.031688446179032326) {
                                        if (x[1] <= 1.0483701825141907) {
                                            return 1;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }

                                    else {
                                        if (x[4] <= 3.656083345413208) {
                                            return 2;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }
                                }

                                else {
                                    if (x[0] <= -0.4079588055610657) {
                                        return 2;
                                    }

                                    else {
                                        if (x[2] <= 1.8156410455703735) {
                                            return 1;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }
                                }
                            }
                        }

                        else {
                            if (x[0] <= -0.03279829956591129) {
                                if (x[0] <= -0.08031384274363518) {
                                    if (x[1] <= 1.2400715351104736) {
                                        if (x[3] <= -5.159601449966431) {
                                            return 2;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }

                                    else {
                                        if (x[0] <= -0.1015620008111) {
                                            return 2;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }
                                }

                                else {
                                    if (x[3] <= -7.706692457199097) {
                                        if (x[5] <= 0.008435785304754972) {
                                            return 1;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }

                                    else {
                                        if (x[4] <= 12.064104080200195) {
                                            return 1;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }
                                }
                            }

                            else {
                                if (x[3] <= -12.982329845428467) {
                                    if (x[4] <= -4.66187310218811) {
                                        if (x[2] <= 1.9739201664924622) {
                                            return 1;
                                        }

                                        else {
                                            return 2;
                                        }
                                    }

                                    else {
                                        if (x[4] <= -3.502048134803772) {
                                            return 1;
                                        }

                                        else {
                                            return 0;
                                        }
                                    }
                                }

                                else {
                                    if (x[3] <= 52.880409240722656) {
                                        if (x[2] <= 1.2790263891220093) {
                                            return 0;
                                        }

                                        else {
                                            return 1;
                                        }
                                    }

                                    else {
                                        return 2;
                                    }
                                }
                            }
                        }
                    }

                    /**
                    * Predict readable class name
                    */
                    const char* predictLabel(float *x) {
                        return idxToLabel(predict(x));
                    }

                    /**
                    * Convert class idx to readable name
                    */
                    const char* idxToLabel(uint8_t classIdx) {
                        switch (classIdx) {
                            case 0:
                            return "NORMAL";
                            case 1:
                            return "NATURAL";
                            case 2:
                            return "ALERT";
                            default:
                            return "Houston we have a problem";
                        }
                    }

                protected:
                };
            }
        }
    }