// ======================================================================
// \title  MathSenderTestMain.cpp
// \author cindy
// \brief  cpp file for MathSender component test main function
// ======================================================================

#include "MathSenderTester.hpp"

TEST(Nominal, toDo) {
  MathModule::MathSenderTester tester;
  tester.toDo();
}

int main(int argc, char** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
